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
    AttestationStore,
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

#: Attestation IDs the test suite and certification scripts emit. A gate bound
#: to one of these is still derived: the attestation is signed with the manager
#: key and verified before it counts, exactly like a receipt.
A_NO_SHELL = "static.no_arbitrary_shell"
A_ROLLBACK_ENABLED = "forced_failure.rollback_enabled_operations"
A_NO_DELETION = "static.no_deletion_capability"
A_KEYCHAIN = "operator.macos_keychain"
A_UI_SETUP = "operator.macos_ui_setup"
A_UI_VALIDATION = "operator.macos_ui_validation"
A_OPERATOR_E2E = "operator.macos_end_to_end"

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

#: Gates verified by inspecting repository state at merge time rather than from
#: any artifact this evaluator can read -- no operation observes git. Listed by
#: id rather than by status so the exemption cannot quietly grow: a new gate
#: does not become merge-exempt by being marked deferred.
MERGE_TIME_VERIFIED = frozenset(
    {"G01_BASELINE_PINNED", "G02_PR94_UNCHANGED", "G23_NO_MERGE"}
)

HUB_SLICE_SCOPE = (
    "TheHub's 13 declared operations -- 12 enabled and executed, hub.fetch declared and "
    "disabled -- on a headless Linux host, plus macOS operator certification of the Hub "
    "app alone. Says nothing about the 55 producer operations or the other six apps."
)

FEDERATION_VECTOR_SCOPE = (
    "The full vector: all 68 operations across all seven apps, including 6-of-6 producer "
    "exports and a 7-of-7 macOS operator pass. Evaluated and published alongside the "
    "gating profile so narrowing scope cannot hide what is still incomplete."
)


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
        required_attestations=[A_NO_SHELL],
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
            "Six strategies are built and certified by forced-failure tests at every boundary: "
            "stage_validate_atomic_promote, file_snapshot_restore, "
            "sqlite_backup_integrity_check_atomic_swap, versioned_install_pointer_swap, "
            "ledger_snapshot_restore, run_partition_restore. Five declared by producer "
            "operations are not built: delete_staging_download, "
            "dispatch_receipt_compensating_remove, queue_run_partition_delete, "
            "transactional_run_partition_restore, "
            "transaction_snapshot_and_run_partition_restore. Partial coverage is not a pass. "
            "Corrects an earlier count of three, which undercounted by inspecting only the "
            "strategies with implementations rather than every value the policy references. A "
            "sixth row carried prose rather than an identifier ('delete staging checkout; "
            "preserve prior current pointer'), which no lookup could match; it has been "
            "normalised to delete_staging_download and the builder now rejects the shape."
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
        required_attestations=[A_NO_DELETION],
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


#: The vector profile: the original 23 gates, measured against all seven apps
#: and all 68 operations. Nothing here is narrowed.
FEDERATION_VECTOR_RULES = GATE_RULES


def _override(rules, changes):
    """Return ``rules`` with the named gates replaced.

    Overriding rather than redefining keeps the two profiles textually close, so
    a reviewer can see exactly which gates a narrower scope changes and read the
    rest once.
    """
    from dataclasses import replace

    unknown = set(changes) - {rule.gate_id for rule in rules}
    if unknown:
        raise KeyError(f"override targets a gate that does not exist: {sorted(unknown)}")
    return [replace(rule, **changes.get(rule.gate_id, {})) for rule in rules]


#: The Hub-slice profile: what PR #99 actually claims. Gates that are inherently
#: about producers or about all seven apps are re-stated at Hub scope, and the
#: macOS gates become attestation-bound rather than blocked, because an operator
#: certification run on a real Mac can now produce that evidence.
HUB_SLICE_RULES = _override(
    GATE_RULES,
    {
        "G07_NATIVE_SECRETS": dict(
            requirement="macOS Keychain provider certified on a real macOS host.",
            blocked_reason="",
            required_attestations=[A_KEYCHAIN],
        ),
        "G13_ATOMIC_ROLLBACK": dict(
            requirement=(
                "Every rollback strategy declared by an ENABLED operation passes forced-failure "
                "rollback at each boundary."
            ),
            deferred_reason="",
            required_attestations=[A_ROLLBACK_ENABLED],
        ),
        "G15_7_OF_7_UI_SETUP": dict(
            requirement="TheHub completes macOS setup through the UI with no Terminal.",
            blocked_reason="",
            required_attestations=[A_UI_SETUP],
        ),
        "G16_7_OF_7_UI_VALIDATION": dict(
            requirement="TheHub runs its validation controls through the UI and retains receipts.",
            blocked_reason="",
            required_attestations=[A_UI_VALIDATION],
        ),
        "G17_6_OF_6_PRODUCER_EXPORTS": dict(
            requirement="Producer exports are out of scope for the Hub slice.",
            deferred_reason=(
                "Inherently a producer gate: it cannot be restated at Hub scope without changing "
                "what it measures, so it is left deferred here and carried at full width in the "
                "federation_vector profile. See docs/FEDERATION_UI_OPERATIONS_HANDOFF_NEXT.md."
            ),
        ),
        "G22_REAL_OPERATOR_MACOS": dict(
            requirement="A macOS operator runs the Hub slice end to end, through to rollback.",
            blocked_reason="",
            required_attestations=[A_OPERATOR_E2E],
        ),
    },
)

#: Gates that measure something the Hub slice deliberately does not do. Distinct
#: from "not finished": no work on this pull request could close them, because
#: closing them would mean enlarging its scope. Enumerated so the exclusion is a
#: reviewable list rather than a property of prose in a status_reason.
HUB_SLICE_OUT_OF_SCOPE = {
    "G09_REPOSITORY_ACQUISITION": (
        "hub.fetch is declared and left disabled, so nothing in this slice acquires a "
        "repository. Carried at full width in federation_vector."
    ),
    "G17_6_OF_6_PRODUCER_EXPORTS": (
        "Producer exports require the 55 producer operations, which this slice does not "
        "enable. Carried at full width in federation_vector."
    ),
}

PROFILES = {
    "hub_slice": (HUB_SLICE_RULES, HUB_SLICE_SCOPE, HUB_SLICE_OUT_OF_SCOPE),
    "federation_vector": (FEDERATION_VECTOR_RULES, FEDERATION_VECTOR_SCOPE, {}),
}

#: Which profile decides whether this pull request may merge.
GATING_PROFILE = "hub_slice"


def merge_readiness(evidence, out_of_scope=None) -> dict:
    """Say plainly whether the gating profile permits a merge, and why not.

    ``deferred`` is not a free pass. A gate may be set aside only two ways, both
    of them enumerated by id rather than inferred from status: it is in
    ``MERGE_TIME_VERIFIED`` (repository state no artifact here can observe), or
    it is declared out of scope for this profile. Anything else that is not
    ``passed`` blocks, so no gate can be excused by writing a reason into it.
    """
    out_of_scope = out_of_scope or {}
    blockers = []
    for gate in evidence["gates"]:
        if not gate.get("blocking", True):
            continue
        status = gate["status"]
        gate_id = gate["gate_id"]
        if status == "passed":
            continue
        if status == "deferred" and gate_id in MERGE_TIME_VERIFIED:
            continue
        if status == "deferred" and gate_id in out_of_scope:
            continue
        blockers.append({"gate_id": gate_id, "status": status})
    return {
        "profile_id": evidence.get("profile_id", ""),
        "ready": not blockers,
        "blocking_gates": blockers,
        "merge_time_verified": sorted(MERGE_TIME_VERIFIED),
        "out_of_scope": dict(sorted(out_of_scope.items())),
    }


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
    parser.add_argument(
        "--attestations",
        type=Path,
        help="Directory of signed attestations. Omit and attestation-bound gates report not_run.",
    )
    parser.add_argument(
        "--attestation-public-key",
        type=Path,
        help=(
            "Public key that signed the attestations. Defaults to --public-key. They differ "
            "whenever an operator certification was produced on the host being certified "
            "rather than on the machine that ran the operations."
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
    documents = store.all_documents()

    attestation_key = (
        args.attestation_public_key.read_bytes() if args.attestation_public_key else None
    )

    attestations = []
    if args.attestations and args.attestations.exists():
        attestations = AttestationStore(
            args.attestations, ReceiptSigner.generate("unused")
        ).all_documents()

    def evaluate(profile_id):
        rules, scope, _ = PROFILES[profile_id]
        return evaluate_gates(
            rules,
            documents,
            public_key_pem=public_key,
            policy_sha256=args.policy_sha256 or None,
            attestations=attestations,
            attestation_public_key_pem=attestation_key,
            profile_id=profile_id,
            profile_scope=scope,
        )

    evidence = evaluate(GATING_PROFILE)
    evidence["additional_profiles"] = {
        profile_id: {
            "profile_scope": PROFILES[profile_id][1],
            "summary": summarize(other),
            "gates": other["gates"],
        }
        for profile_id in PROFILES
        if profile_id != GATING_PROFILE
        for other in [evaluate(profile_id)]
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"wrote {args.out}")
    print(f"gating profile: {GATING_PROFILE}")
    for status, count in summarize(evidence).items():
        print(f"  {status}: {count}")
    for profile_id, block in evidence["additional_profiles"].items():
        print(f"also evaluated: {profile_id}")
        for status, count in block["summary"].items():
            print(f"  {status}: {count}")

    readiness = merge_readiness(evidence, PROFILES[GATING_PROFILE][2])
    if readiness["ready"]:
        print(f"\nmerge readiness ({GATING_PROFILE}): READY")
    else:
        print(f"\nmerge readiness ({GATING_PROFILE}): NOT READY")
        for blocker in readiness["blocking_gates"]:
            print(f"  {blocker['gate_id']}: {blocker['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
