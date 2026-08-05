#!/usr/bin/env python3
"""Assemble the Federation Manager runtime and serve it.

``federation_manager_api.runtime`` is ``None`` at import, and every operations
endpoint refuses with 503 until something assigns it. ``ManagerRuntime``'s
docstring says it is "assembled by the native host" -- this is that host, minus
the packaging. Without it ``uvicorn server.backend.main:app`` mounts the router
but serves a manager whose entire operations surface is unavailable, which is
what made the first real operator certification refute all four gates with the
same ``HTTPError 503``.

This is deliberately a separate entry point rather than a startup hook in
``main.py``. The operations plane owns real credentials, spawns processes, and
writes signed receipts; wiring it into the general application would mean every
deployment of the Hub carried an execution surface whether or not it wanted one.
Here it is opt-in, and the process that runs it is the one that was configured
for it.

Usage::

    export PRII_MANAGER_BOOTSTRAP_NONCE="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
    export PRII_MANAGER_RECEIPT_SIGNING_KEY="$HOME/.prii/manager.pem"
    python3 scripts/run_manager_host.py

State (receipts, staging, intake) lives under ``--state-root``, default
``~/.prii/manager``. Nothing is written inside the repository.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from server.backend import federation_manager_api as api  # noqa: E402
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


class HostRefused(RuntimeError):
    """Raised when the host cannot be assembled to a trustworthy state."""


def _pinned_key_id(document) -> str:
    """Take the pinned identity from the document the committed key signed.

    Not a constant: the pin's job is to make a *substituted* policy fail, and it
    does that through the signature check against ``operations_policy_key.pub``.
    Hard-coding the id here as well would mean editing this file every time the
    policy is legitimately re-keyed, and a stale constant fails in a way that
    looks like tampering.
    """
    return document["signature"]["key_id"]


def build_runtime(state_root: Path, app_root: Path):
    """Assemble the runtime, refusing rather than degrading."""
    if not POLICY_PATH.exists():
        raise HostRefused(f"no operations policy at {POLICY_PATH}")

    document = load_policy_document(POLICY_PATH)
    try:
        policy = verify_policy(
            document,
            schema=json.loads(POLICY_SCHEMA_PATH.read_text(encoding="utf-8")),
            public_key_pem=POLICY_KEY_PATH.read_bytes(),
            pinned_key_id=_pinned_key_id(document),
        )
    except PolicySignatureError as exc:
        # A policy the manager cannot fully trust must not select an executable.
        raise HostRefused(f"operations policy failed verification: {exc}") from exc

    try:
        signer = signer_from_environment("prii-manager-local")
    except ReceiptError as exc:
        raise HostRefused(str(exc)) from exc

    if not os.environ.get(RECEIPT_SIGNING_KEY_ENV, "").strip():
        # signer_from_environment falls back to an ephemeral key with a warning.
        # For a host that exists to produce gate evidence that is not good
        # enough: receipts written now would stop verifying at the next restart,
        # silently, and gates derived from them would quietly stop deriving.
        raise HostRefused(
            f"{RECEIPT_SIGNING_KEY_ENV} is unset. Receipts signed with an ephemeral key "
            "stop verifying when this process exits, so gate evidence produced against "
            "them is worthless. Point it at a persisted key."
        )

    for name in ("receipts", "staging", "intake", "data"):
        (state_root / name).mkdir(parents=True, exist_ok=True)

    files = FileTokenBroker(state_root / "intake")
    secrets = SecretBroker(select_provider())

    runner = OperationRunner(
        policy=policy,
        context=ExecutionContext(
            app_root=app_root,
            data_root=state_root / "data",
            staging_root=state_root / "staging",
            intake_root=state_root / "intake",
        ),
        receipts=ReceiptStore(
            state_root / "receipts",
            signer,
            schema=json.loads(RECEIPT_SCHEMA_PATH.read_text(encoding="utf-8")),
        ),
        files=files,
        secrets=secrets,
    )

    # Imported lazily: tools/ is not a package the server depends on, and a
    # missing gate module should not stop the operations surface from serving.
    try:
        sys.path.insert(0, str(REPO_ROOT / "tools"))
        from evaluate_federation_gates import HUB_SLICE_RULES as gate_rules
    except Exception:  # noqa: BLE001 - gates are reporting, not a serving concern
        gate_rules = ()

    return api.ManagerRuntime(
        runner=runner, files=files, secrets_broker=secrets, gate_rules=gate_rules
    ), policy


def _session_bootstrap_snippet(nonce: str) -> str:
    """The browser needs a session token in sessionStorage; nothing puts it there.

    `managerClient.js` reads `prii.manager.session` from sessionStorage and
    refuses when it is absent, but no code in the SPA performs the exchange --
    that was the native host's job too. Until the host is packaged, the operator
    runs this in the App Center's console. It is re-runnable, which matters
    because the session TTL is five minutes.
    """
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
        help="where receipts, staging and intake live (default ~/.prii/manager)",
    )
    parser.add_argument(
        "--app-root",
        type=Path,
        default=REPO_ROOT,
        help="the application root operations run against (default: this repository)",
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
        runtime, policy = build_runtime(args.state_root.expanduser(), args.app_root.expanduser())
    except HostRefused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2

    api.runtime = runtime

    enabled = sum(1 for op in policy.operations.values() if getattr(op, "enabled", False))
    print(f"manager host on http://{args.host}:{args.port}")
    print(f"  policy       : {len(policy.operations)} operations, {enabled} enabled")
    print(f"  secrets      : {provider_description(select_provider())['name']}")
    print(f"  state root   : {args.state_root}")
    print(f"  app root     : {args.app_root}")
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
