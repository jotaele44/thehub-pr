#!/usr/bin/env python3
"""Assemble the Federation Manager runtime and serve it.

The manager is opt-in because it owns credentials, spawns supervised processes,
and writes signed receipts. The runtime binds each signed-policy repository to a
verified checkout inside one workspace instead of applying every operation to
TheHub's root.

Usage::

    export PRII_MANAGER_BOOTSTRAP_NONCE="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
    export PRII_MANAGER_RECEIPT_SIGNING_KEY="$HOME/.prii/manager.pem"
    python3 scripts/run_manager_host.py --workspace-root ..

State (receipts, staging, intake, data, artifacts) lives under ``--state-root``,
default ``~/.prii/manager``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from server.backend import federation_manager_api as api  # noqa: E402
from server.backend.federation_manager_artifacts import ArtifactStore  # noqa: E402
from server.backend.federation_manager_files import FileTokenBroker  # noqa: E402
from server.backend.federation_manager_operations import (  # noqa: E402
    ExecutionContext,
    PolicySignatureError,
    load_policy_document,
    verify_policy,
)
from server.backend.federation_manager_receipts import (  # noqa: E402
    RECEIPT_SIGNING_KEY_ENV,
    ReceiptError,
    ReceiptStore,
    signer_from_environment,
)
from server.backend.federation_manager_repository_registry import (  # noqa: E402
    RepositoryBindingError,
    WorkspaceRepositoryRegistry,
)
from server.backend.federation_manager_repository_runner import RepositoryOperationRouter  # noqa: E402
from server.backend.federation_manager_runner import OperationRunner  # noqa: E402
from server.backend.federation_manager_secrets import (  # noqa: E402
    SecretBroker,
    provider_description,
    select_provider,
)

POLICY_PATH = REPO_ROOT / "config" / "operations_policy.json"
POLICY_KEY_PATH = REPO_ROOT / "config" / "operations_policy_key.pub"
POLICY_SCHEMA_PATH = REPO_ROOT / "schemas" / "signed_command_policy.schema.json"
RECEIPT_SCHEMA_PATH = REPO_ROOT / "schemas" / "execution_receipt.schema.json"
PRODUCER_REGISTRY_PATH = REPO_ROOT / "registry" / "producers.yaml"


class HostRefused(RuntimeError):
    """Raised when the host cannot be assembled to a trustworthy state."""


def _pinned_key_id(document) -> str:
    return document["signature"]["key_id"]


def _verified_policy():
    if not POLICY_PATH.exists():
        raise HostRefused(f"no operations policy at {POLICY_PATH}")
    document = load_policy_document(POLICY_PATH)
    try:
        return verify_policy(
            document,
            schema=json.loads(POLICY_SCHEMA_PATH.read_text(encoding="utf-8")),
            public_key_pem=POLICY_KEY_PATH.read_bytes(),
            pinned_key_id=_pinned_key_id(document),
        )
    except PolicySignatureError as exc:
        raise HostRefused(f"operations policy failed verification: {exc}") from exc


def build_runtime(
    state_root: Path,
    app_root: Path,
    workspace_root: Optional[Path] = None,
):
    """Assemble a repository-aware runtime, refusing rather than degrading trust."""
    policy = _verified_policy()

    try:
        signer = signer_from_environment("prii-manager-local")
    except ReceiptError as exc:
        raise HostRefused(str(exc)) from exc

    if not os.environ.get(RECEIPT_SIGNING_KEY_ENV, "").strip():
        raise HostRefused(
            f"{RECEIPT_SIGNING_KEY_ENV} is unset. Receipts signed with an ephemeral key "
            "stop verifying when this process exits, so gate evidence produced against "
            "them is worthless. Point it at a persisted key."
        )

    state_root = Path(state_root).expanduser().resolve()
    app_root = Path(app_root).expanduser().resolve()
    workspace_root = Path(workspace_root or app_root.parent).expanduser().resolve()

    for name in ("receipts", "staging", "intake", "data", "artifacts"):
        (state_root / name).mkdir(parents=True, exist_ok=True)

    files = FileTokenBroker(state_root / "intake")
    secrets = SecretBroker(select_provider())
    receipts = ReceiptStore(
        state_root / "receipts",
        signer,
        schema=json.loads(RECEIPT_SCHEMA_PATH.read_text(encoding="utf-8")),
    )

    try:
        repositories = WorkspaceRepositoryRegistry(
            workspace_root=workspace_root,
            hub_root=app_root,
            producer_registry_path=PRODUCER_REGISTRY_PATH,
        )
    except RepositoryBindingError as exc:
        raise HostRefused(f"repository registry could not be trusted: {exc}") from exc

    runners = {}
    hub_binding = repositories.resolve("thehub-pr")
    runners["thehub-pr"] = OperationRunner(
        policy=policy,
        context=ExecutionContext(
            app_root=hub_binding.root,
            data_root=state_root / "data",
            staging_root=state_root / "staging" / "thehub",
            intake_root=state_root / "intake",
        ),
        receipts=receipts,
        files=files,
        secrets=secrets,
    )

    required_repo_keys = sorted(
        {operation.repo for operation in policy.operations.values() if operation.repo != "thehub-pr"}
    )
    binding_failures = {}
    for repo_key in required_repo_keys:
        try:
            binding = repositories.resolve(repo_key)
        except RepositoryBindingError as exc:
            binding_failures[repo_key] = str(exc)
            continue
        runners[repo_key] = OperationRunner(
            policy=policy,
            context=ExecutionContext(
                app_root=binding.root,
                data_root=binding.root,
                staging_root=state_root / "staging" / binding.app_id,
                intake_root=state_root / "intake",
            ),
            receipts=receipts,
            files=files,
            secrets=secrets,
        )

    runner = RepositoryOperationRouter(policy=policy, runners=runners)

    try:
        sys.path.insert(0, str(REPO_ROOT / "tools"))
        from evaluate_federation_gates import HUB_SLICE_RULES as gate_rules
    except Exception:  # noqa: BLE001 - gates are reporting, not a serving concern
        gate_rules = ()

    runtime = api.ManagerRuntime(
        runner=runner,
        files=files,
        secrets_broker=secrets,
        gate_rules=gate_rules,
    )
    # Runtime attachments are intentionally explicit but additive so existing
    # API consumers that only know runner/files/secrets keep working unchanged.
    runtime.repositories = repositories
    runtime.artifacts = ArtifactStore(state_root / "artifacts")
    runtime.repository_binding_failures = binding_failures
    return runtime, policy


def _session_bootstrap_snippet(nonce: str) -> str:
    return (
        "fetch('/api/federation-manager/session',{method:'POST',"
        "headers:{'Content-Type':'application/json'},"
        f"body:JSON.stringify({{nonce:'{nonce}',origin:location.origin}})}})"
        ".then(r=>r.json()).then(d=>{sessionStorage.setItem('prii.manager.session',d.token);"
        "console.log('manager session set, expires',d.expiresAt)})"
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--state-root",
        type=Path,
        default=Path.home() / ".prii" / "manager",
        help="where receipts, staging, intake and artifacts live (default ~/.prii/manager)",
    )
    parser.add_argument(
        "--app-root",
        type=Path,
        default=REPO_ROOT,
        help="TheHub application root (default: this repository)",
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=REPO_ROOT.parent,
        help="parent workspace containing registered producer checkouts",
    )
    args = parser.parse_args(argv)

    nonce = os.environ.get("PRII_MANAGER_BOOTSTRAP_NONCE", "").strip()
    if not nonce:
        print(
            "refused: PRII_MANAGER_BOOTSTRAP_NONCE is unset. The manager API reads it at "
            "import time to authorise session exchange; without it POST /session answers "
            "503 and no client can reach the operations surface.",
            file=sys.stderr,
        )
        return 2

    try:
        runtime, policy = build_runtime(
            args.state_root.expanduser(),
            args.app_root.expanduser(),
            args.workspace_root.expanduser(),
        )
    except HostRefused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2

    api.runtime = runtime

    enabled = sum(1 for op in policy.operations.values() if getattr(op, "enabled", False))
    print(f"manager host on http://{args.host}:{args.port}")
    print(f"  policy       : {len(policy.operations)} operations, {enabled} enabled")
    print(f"  repositories : {', '.join(runtime.runner.repository_keys)}")
    if runtime.repository_binding_failures:
        print(f"  unavailable  : {len(runtime.repository_binding_failures)} registered checkout(s)")
    print(f"  secrets      : {provider_description(select_provider())['name']}")
    print(f"  state root   : {args.state_root}")
    print(f"  workspace    : {args.workspace_root}")
    print()
    print("The App Center needs a session token in sessionStorage. Open it on an allowed")
    print("origin and run this in the browser console (re-run when it expires):")
    print()
    print(f"  {_session_bootstrap_snippet(nonce)}")
    print()

    import uvicorn  # noqa: PLC0415 - only needed when actually serving

    from server.backend.main import app

    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
