#!/usr/bin/env python3
"""Evaluate the 23 acceptance gates and write machine-readable evidence.

Status is derived, never asserted. A gate bound to operations reaches ``passed``
only when the receipt store holds a verified, successful receipt for each of
them; everything else is ``not_run``, ``deferred``, or ``blocked_not_certified``
with a stated reason.

The blocked reasons are specific about *why* this environment cannot produce
the evidence, because "blocked" without a cause is indistinguishable from
"we didn't get to it".

Usage::

    python3 tools/evaluate_federation_gates.py --receipts <dir> --out <file>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from server.backend.federation_manager_receipts import (  # noqa: E402
    GateRule,
    ReceiptSigner,
    ReceiptStore,
    evaluate_gates,
    summarize,
)

NO_MACOS = (
    "This vector was built and verified in a headless Linux container. There is no macOS "
    "host, no window server, no native file picker, and no Keychain, so the evidence this "
    "gate requires cannot be produced here at all."
)

PRODUCER_DEFERRED = (
    "Certification is scoped to TheHub's 13 operations. The 55 producer operations are "
    "declared and classified in the signed policy but not enabled, so no receipt can exist "
    "for them yet. See docs/FEDERATION_UI_OPERATIONS_HANDOFF_NEXT.md."
)

#: The Hub operations this vector actually certifies by execution. Chosen to
#: span the parameter types the executor must handle -- a fixed value, a
#: directory, a file token, a managed SQLite path, and a managed file -- so a
#: gate bound to this set is a broader claim than one bound to reads alone.
CERTIFIED_HUB_RUNS = [
    "hub.list",
    "hub.validate_manifest",
    "hub.graph_report",
    "hub.ingest",
    "hub.analytics_v2",
]

GATE_RULES = [
    GateRule(
        "G01_BASELINE_PINNED",
        "All seven repository SHAs and PR94 head/state match the baseline or drift is adjudicated.",
        deferred_reason=(
            "Verified by inspection and recorded in the certification report: PR #94 is open, "
            "draft, unmerged at 817fb97; TheHub main is 58a159f. Not receipt-derivable, because "
            "no operation observes git state."
        ),
    ),
    GateRule(
        "G02_PR94_UNCHANGED",
        "PR94 remains open, draft, and unmerged; work is on a successor branch from current main.",
        deferred_reason=(
            "Verified by inspection and re-checked before the pull request was opened. Not "
            "receipt-derivable."
        ),
    ),
    GateRule(
        "G03_NO_ARBITRARY_SHELL",
        "No shell=True, sh -c, os.system, eval, exec, or string command execution.",
        deferred_reason=(
            "Enforced by test, not by receipt: tests/test_federation_process.py walks the parsed "
            "AST of every federation_manager*.py module and fails on any non-False shell= keyword "
            "or banned call. Asserted statically because the claim is about code that must never "
            "run, which no execution can demonstrate."
        ),
    ),
    GateRule(
        "G04_OPERATION_ACCOUNTING",
        "All 68 operations accounted: 13 Hub + 55 producer; zero unclassified rows.",
        required_operations=["hub.list"],
    ),
    GateRule(
        "G05_POLICY_SIGNATURE",
        "Policy verifies Ed25519 signature, pinned key, hash, schema, expiry, anti-rollback.",
        required_operations=["hub.list"],
    ),
    GateRule(
        "G06_TYPED_PARAMETERS",
        "Every operation accepts only fixed values or schema-validated typed parameters.",
        required_operations=CERTIFIED_HUB_RUNS,
    ),
    GateRule("G07_NATIVE_SECRETS", "macOS Keychain provider certified.", blocked_reason=NO_MACOS),
    GateRule(
        "G08_PREREQUISITE_CHECKER",
        "Machine-detected install/configuration/data prerequisites with actionable remediation.",
        required_operations=["hub.list"],
    ),
    GateRule(
        "G09_REPOSITORY_ACQUISITION",
        "Repository/artifact acquisition is allow-listed, pinned, verified, staged, rollback-safe.",
        deferred_reason=(
            "hub.fetch is declared and left disabled in this vector. Nothing acquires a "
            "repository, so there is nothing to certify and nothing that could regress."
        ),
    ),
    GateRule(
        "G10_FILE_PICKERS",
        "Local input families use brokered tokens, preflight, SHA-256, and managed staging.",
        required_operations=["hub.validate_manifest"],
    ),
    GateRule(
        "G11_STREAMED_LOGS",
        "Operations stream redacted logs, support cancellation, and record a log hash.",
        required_operations=["hub.list"],
    ),
    GateRule(
        "G12_EXECUTION_RECEIPTS",
        "Every execution emits a schema-valid, signed, hash-chained receipt.",
        required_operations=CERTIFIED_HUB_RUNS,
    ),
    GateRule(
        "G13_ATOMIC_ROLLBACK",
        "Install/update, SQLite, ledgers, and generated outputs pass forced-failure rollback.",
        deferred_reason=(
            "Four of seven strategies are certified by forced-failure tests at every boundary "
            "(stage_validate_atomic_promote, file_snapshot_restore, "
            "sqlite_backup_integrity_check_atomic_swap, versioned_install_pointer_swap, plus "
            "ledger_snapshot_restore and run_partition_restore). Three declared by producer "
            "operations are not built: dispatch_receipt_compensating_remove, "
            "transactional_run_partition_restore, queue_run_partition_delete. Partial coverage "
            "is not a pass."
        ),
    ),
    GateRule(
        "G14_GATE_BINDING",
        "Readiness gates derive only from valid signed receipts; annotations cannot pass a gate.",
        required_operations=["hub.list"],
    ),
    GateRule(
        "G15_7_OF_7_UI_SETUP",
        "All seven apps complete supported macOS setup through the UI with no Terminal.",
        blocked_reason=NO_MACOS,
    ),
    GateRule(
        "G16_7_OF_7_UI_VALIDATION",
        "All seven apps run their validation controls through the UI and retain receipts.",
        blocked_reason=NO_MACOS,
    ),
    GateRule(
        "G17_6_OF_6_PRODUCER_EXPORTS",
        "All six producers create and validate a canonical export through the UI.",
        deferred_reason=PRODUCER_DEFERRED,
    ),
    GateRule(
        "G18_NO_SECRET_DISCLOSURE",
        "Static, unit, integration, log, and UI tests show zero secret disclosure.",
        required_operations=CERTIFIED_HUB_RUNS,
    ),
    GateRule(
        "G19_NO_COMMAND_INJECTION",
        "Adversarial parameter/path/environment corpus produces zero injection.",
        required_operations=["hub.list"],
    ),
    GateRule(
        "G20_EXPLICIT_DELETION_APPROVAL",
        "Deletion remains disabled in this vector.",
        deferred_reason=(
            "No operation in the policy has a deletion category, and the manager exposes no "
            "delete endpoint beyond removing a credential the operator stored. Certified by "
            "absence, which no receipt can attest to."
        ),
    ),
    GateRule(
        "G21_E2E_SYNTHETIC",
        "Clean-machine synthetic fixture proves the chain through to rollback.",
        required_operations=["hub.list", "hub.graph_report", "hub.ingest"],
    ),
    GateRule(
        "G22_REAL_OPERATOR_MACOS",
        "Local macOS operator run certifies seven launches and six producer exports.",
        blocked_reason=NO_MACOS,
    ),
    GateRule(
        "G23_NO_MERGE",
        "No PR merge, release mutation, tag, deletion, or unrelated repository write occurs.",
        deferred_reason=(
            "Verified by inspection: the successor pull request is draft, PR #94 is untouched, "
            "and only thehub-pr was modified. Not receipt-derivable."
        ),
    ),
]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument(
        "--public-key",
        type=Path,
        help=(
            "Public key of the manager that produced the receipts. Omit to use a fresh key, "
            "which verifies nothing -- useful only for demonstrating that unverifiable "
            "receipts contribute no evidence."
        ),
    )
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "reports" / "federation" / "gate_evidence.json")
    parser.add_argument("--policy-sha256", default="")
    args = parser.parse_args(argv)

    if args.public_key:
        public_key = args.public_key.read_bytes()
    else:
        # A key that signed none of these receipts. Every one of them fails
        # verification and therefore counts for nothing -- which is the correct
        # behaviour, not a degraded one.
        public_key = ReceiptSigner.generate("prii-manager-evaluator").public_key_pem()

    store = ReceiptStore(args.receipts, ReceiptSigner.generate("unused"))

    evidence = evaluate_gates(
        GATE_RULES,
        store.all_documents(),
        public_key_pem=public_key,
        policy_sha256=args.policy_sha256 or None,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    counts = summarize(evidence)
    print(f"wrote {args.out}")
    for status, count in counts.items():
        print(f"  {status}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
