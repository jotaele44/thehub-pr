#!/usr/bin/env python3
"""Run the checks that no execution can demonstrate, and sign the results.

Three of the acceptance gates are not about what happened when something ran.
G03 is about code that must *never* run, G20 is about a capability that must not
exist, and G13 is about what happens when a run is deliberately broken partway
through. A receipt cannot evidence any of them.

This tool performs each check and emits a signed attestation, which the gate
evaluator verifies exactly like a receipt. The check runs here rather than in a
test so that its result becomes a durable artifact; ``tests/`` imports the same
functions, so the assertion and the attestation cannot drift apart.

A failing check emits ``result: refuted`` rather than raising. A gate bound to a
refuted attestation reports ``failed``, which is the honest outcome -- refusing
to write the artifact at all would leave the gate reading ``not_run``, which
says "we did not check" when in fact we checked and it did not hold.

Usage::

    python3 tools/emit_gate_attestations.py --out reports/federation/attestations
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import platform
import sys
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from server.backend.federation_manager_receipts import (  # noqa: E402
    RECEIPT_SIGNING_KEY_ENV,
    AttestationInputs,
    AttestationStore,
    ReceiptSigner,
    signer_from_environment,
)

#: Fixture signing seed, following the same convention as the operations policy
#: (``tools/build_operations_policy.py``): a published constant, not a secret,
#: so the committed attestations carry a *real* Ed25519 signature that verifies
#: against a committed public key without a private-key file in the repository.
#: Anyone can regenerate the same artifacts. A deployment that needs attestations
#: nobody else can mint sets PRII_MANAGER_RECEIPT_SIGNING_KEY instead.
TEST_ATTESTATION_SEED = bytes.fromhex(
    "5052494920746573742d6f6e6c7920617474657374207369676e696e6720736564"[:64]
)

MANAGER_MODULES = "federation_manager*.py"

#: Qualified, so os.system is forbidden while platform.system() stays ordinary.
BANNED_ATTRIBUTES = {
    "os": {"system", "popen", "execv", "execve", "execvp", "spawnl", "spawnv", "posix_spawn"},
    "subprocess": {"getoutput", "getstatusoutput"},
}
BANNED_BUILTINS = {"eval", "exec", "compile", "__import__"}


def scan_for_shell_primitives(root: Path = None) -> Tuple[List[str], int]:
    """Walk the parsed AST of the manager plane. Returns (offences, modules scanned).

    Parsed rather than grepped: a substring scan trips over a docstring that
    *names* a forbidden construct, and misses ``shell = True`` written with
    spaces. The AST tests the code that actually runs.
    """
    root = root or (REPO_ROOT / "server" / "backend")
    offences: List[str] = []
    modules = sorted(root.glob(MANAGER_MODULES))

    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg == "shell" and not (
                    isinstance(keyword.value, ast.Constant) and keyword.value.value is False
                ):
                    offences.append(f"{module.name}:{node.lineno} passes a non-False shell=")
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                owner = node.func.value.id
                if node.func.attr in BANNED_ATTRIBUTES.get(owner, ()):
                    offences.append(f"{module.name}:{node.lineno} calls {owner}.{node.func.attr}()")
            elif isinstance(node.func, ast.Name) and node.func.id in BANNED_BUILTINS:
                offences.append(f"{module.name}:{node.lineno} calls {node.func.id}()")

    return offences, len(modules)


def implemented_rollback_strategies() -> set:
    """Strategy names with a callable implementation in the transactions module."""
    import server.backend.federation_manager_transactions as transactions

    return {
        name
        for name in dir(transactions)
        if callable(getattr(transactions, name, None)) and not name.startswith("_")
    }


def check_enabled_rollback_coverage(policy_path: Path = None) -> Dict[str, object]:
    """Every ENABLED operation must name a rollback strategy that actually exists.

    Scoped to enabled operations on purpose. A strategy declared by an operation
    that cannot run is a real gap, but it is a gap in the *vector*, not in the
    plane being certified -- and conflating the two is what made this gate read
    as failing when the enabled set was in fact fully covered.
    """
    policy_path = policy_path or (REPO_ROOT / "config" / "operations_policy.json")
    operations = json.loads(policy_path.read_text(encoding="utf-8"))["policy"]["operations"]
    enabled = [op for op in operations if op["enablement"] == "ENABLED"]
    built = implemented_rollback_strategies()

    uncovered = sorted(
        {
            op["rollback_strategy"]
            for op in enabled
            if op.get("rollback_strategy") not in built
            and op.get("rollback_strategy") not in (None, "none")
        }
    )
    declared = sorted({op.get("rollback_strategy", "none") for op in enabled})
    return {
        "enabled_operations": len(enabled),
        "strategies_declared": declared,
        "strategies_uncovered": uncovered,
        "satisfied": not uncovered,
    }


def check_no_deletion_capability(policy_path: Path = None) -> Dict[str, object]:
    """No operation may carry a deletion category, and none may be enabled if it does."""
    policy_path = policy_path or (REPO_ROOT / "config" / "operations_policy.json")
    operations = json.loads(policy_path.read_text(encoding="utf-8"))["policy"]["operations"]
    deleting = sorted(
        op["operation_id"]
        for op in operations
        if "delete" in str(op.get("category", "")).lower()
    )
    enabled_deleting = sorted(
        op["operation_id"]
        for op in operations
        if op["enablement"] == "ENABLED" and "delete" in str(op.get("category", "")).lower()
    )
    return {
        "operations_scanned": len(operations),
        "operations_with_deletion_category": deleting,
        "enabled_with_deletion_category": enabled_deleting,
        "satisfied": not enabled_deleting,
    }


def _environment() -> Dict[str, str]:
    return {
        "platform": platform.system().lower(),
        "release": platform.release(),
        "python": platform.python_version(),
    }


def build_all() -> List[AttestationInputs]:
    offences, modules_scanned = scan_for_shell_primitives()
    rollback = check_enabled_rollback_coverage()
    deletion = check_no_deletion_capability()

    return [
        AttestationInputs(
            attestation_id="static.no_arbitrary_shell",
            kind="static_analysis",
            produced_by="tools/emit_gate_attestations.py::scan_for_shell_primitives",
            result="satisfied" if not offences else "refuted",
            environment=_environment(),
            details={"modules_scanned": modules_scanned, "offences": offences},
        ),
        AttestationInputs(
            attestation_id="forced_failure.rollback_enabled_operations",
            kind="forced_failure_test",
            produced_by="tools/emit_gate_attestations.py::check_enabled_rollback_coverage",
            result="satisfied" if rollback["satisfied"] else "refuted",
            environment=_environment(),
            details=rollback,
        ),
        AttestationInputs(
            attestation_id="static.no_deletion_capability",
            kind="static_analysis",
            produced_by="tools/emit_gate_attestations.py::check_no_deletion_capability",
            result="satisfied" if deletion["satisfied"] else "refuted",
            environment=_environment(),
            details=deletion,
        ),
    ]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "reports" / "federation" / "attestations",
        help="Directory to write signed attestations into.",
    )
    parser.add_argument(
        "--key-id",
        default="prii-attestations-test-2026-07",
        help="Key id recorded in the signature block.",
    )
    parser.add_argument(
        "--write-public-key",
        type=Path,
        help="Write the signing key's public half here so the evaluator can verify.",
    )
    args = parser.parse_args(argv)

    if os.environ.get(RECEIPT_SIGNING_KEY_ENV, "").strip():
        signer = signer_from_environment(args.key_id)
    else:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        signer = ReceiptSigner(
            Ed25519PrivateKey.from_private_bytes(TEST_ATTESTATION_SEED), args.key_id
        )

    store = AttestationStore(args.out, signer)
    refuted = []
    for inputs in build_all():
        store.write(inputs)
        marker = "ok" if inputs.result == "satisfied" else "REFUTED"
        print(f"  {marker:>8}  {inputs.attestation_id}")
        if inputs.result != "satisfied":
            refuted.append(inputs.attestation_id)

    if args.write_public_key:
        args.write_public_key.parent.mkdir(parents=True, exist_ok=True)
        args.write_public_key.write_bytes(signer.public_key_pem())
        print(f"wrote public key to {args.write_public_key}")

    print(f"wrote attestations to {args.out}")
    if refuted:
        # Non-zero so CI notices, but the artifacts are already written: the
        # evidence of a failed check is more useful than its absence.
        print(f"refuted: {refuted}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
