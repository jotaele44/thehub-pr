"""Signed, hash-chained receipts and machine-derived gate status.

Covers gates G12 (every execution emits a schema-valid, signed, hash-chained
receipt) and G14 (readiness gates derive only from verified receipts; manual
annotations cannot change status to passed).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

pytest.importorskip("cryptography")

from server.backend.federation_manager_receipts import (  # noqa: E402
    GateRule,
    ReceiptError,
    ReceiptInputs,
    ReceiptSigner,
    ReceiptStore,
    annotate,
    evaluate_gates,
    receipts_for_operation,
    summarize,
    verify_receipt,
    write_gate_evidence,
)

RECEIPT_SCHEMA = json.loads(
    (REPO_ROOT / "schemas" / "execution_receipt.schema.json").read_text(encoding="utf-8")
)
GATE_SCHEMA = json.loads(
    (REPO_ROOT / "schemas" / "gate_evidence.schema.json").read_text(encoding="utf-8")
)

CANARY = "prii-canary-secret-8ae2f1"


def make_inputs(run_id: str, operation_id: str = "hub.list", status: str = "succeeded"):
    return ReceiptInputs(
        run_id=run_id,
        operation_id=operation_id,
        app_id="thehub",
        policy_id="prii-federation-ui-only-operations",
        policy_sequence=1,
        policy_sha256="a" * 64,
        policy_key_id="prii-operations-test-2026-07",
        status=status,
        started_at="2026-07-27T10:00:00Z",
        finished_at="2026-07-27T10:00:05Z",
        argv_redacted=["hub", "list", "--registry", "registry/producers.yaml"],
        argv_sha256="b" * 64,
        parameters_redacted={"registry": "registry/producers.yaml"},
        environment_allowlist=["HOME", "PATH"],
        transaction={
            "strategy": "none",
            "phase_reached": "RECEIPT",
            "rollback_state": "not_required",
            "snapshot_sha256": None,
        },
        log_sha256="c" * 64,
        log_bytes=128,
        log_truncated=False,
        log_redactions=0,
        exit_code=0,
        validators=[{"name": "exit_code", "status": "passed"}],
    )


@pytest.fixture
def signer():
    return ReceiptSigner.generate("prii-manager-test")


@pytest.fixture
def store(tmp_path, signer):
    return ReceiptStore(tmp_path / "receipts", signer, schema=RECEIPT_SCHEMA)


# ── G12: receipts are schema-valid, signed, and chained ─────────────────────


def test_receipt_is_schema_valid_and_signed(store, signer):
    document = store.append(make_inputs("a" * 32))
    digest = verify_receipt(document, public_key_pem=signer.public_key_pem(), schema=RECEIPT_SCHEMA)
    assert digest == document["signature"]["payload_sha256"]
    assert document["signature"]["algorithm"] == "Ed25519"


def test_first_receipt_has_a_null_predecessor(store):
    document = store.append(make_inputs("a" * 32))
    assert document["receipt"]["previous_receipt_sha256"] is None


def test_receipts_chain_to_their_predecessor(store):
    first = store.append(make_inputs("a" * 32))
    second = store.append(make_inputs("b" * 32))
    assert second["receipt"]["previous_receipt_sha256"] == first["signature"]["payload_sha256"]
    assert store.verify_chain() == []


def test_tampering_with_a_stored_receipt_is_detected(store, tmp_path):
    store.append(make_inputs("a" * 32))
    path = store.path_for("a" * 32)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["receipt"]["status"] = "succeeded" if document["receipt"]["status"] != "succeeded" else "failed"
    path.write_text(json.dumps(document), encoding="utf-8")

    problems = store.verify_chain()
    assert problems and "digest does not match" in problems[0]


def test_removing_a_receipt_breaks_the_chain(store):
    store.append(make_inputs("a" * 32))
    store.append(make_inputs("b" * 32))
    store.path_for("a" * 32).unlink()

    problems = store.verify_chain()
    assert problems and "predecessor" in problems[0]


def test_a_receipt_signed_by_another_key_does_not_verify(store, signer):
    document = store.append(make_inputs("a" * 32))
    attacker = ReceiptSigner.generate("attacker")
    with pytest.raises(ReceiptError, match="verification failed"):
        verify_receipt(document, public_key_pem=attacker.public_key_pem())


def test_verify_raises_rather_than_returning_false(store, signer):
    """A boolean return invites an unchecked call site."""
    document = store.append(make_inputs("a" * 32))
    document["signature"]["payload_sha256"] = "0" * 64
    with pytest.raises(ReceiptError):
        verify_receipt(document, public_key_pem=signer.public_key_pem())


def test_receipt_records_argv_as_a_list_not_a_command_line(store):
    document = store.append(make_inputs("a" * 32))
    argv = document["receipt"]["argv_redacted"]
    assert isinstance(argv, list)
    assert all(isinstance(item, str) for item in argv)


def test_receipt_carries_no_secret_values(store):
    data = make_inputs("a" * 32)
    data.environment_allowlist = ["ANTHROPIC_API_KEY", "PATH"]
    document = store.append(data)
    serialised = json.dumps(document)
    assert CANARY not in serialised
    assert "ANTHROPIC_API_KEY" in serialised, "names are recorded"


def test_failed_run_produces_a_receipt_too(store):
    document = store.append(make_inputs("d" * 32, status="failed"))
    assert document["receipt"]["status"] == "failed"


def test_rolled_back_run_records_its_rollback_state(store):
    data = make_inputs("e" * 32, status="rolled_back")
    data.transaction = {
        "strategy": "stage_validate_atomic_promote",
        "phase_reached": "COMMIT",
        "rollback_state": "succeeded",
        "snapshot_sha256": "f" * 64,
        "rollback_detail": "failure after commit",
    }
    document = store.append(data)
    assert document["receipt"]["transaction"]["rollback_state"] == "succeeded"


def test_store_load_round_trips(store):
    store.append(make_inputs("a" * 32))
    assert store.load("a" * 32)["receipt"]["run_id"] == "a" * 32


def test_loading_an_unknown_run_raises(store):
    with pytest.raises(ReceiptError, match="no receipt"):
        store.load("f" * 32)


def test_receipts_for_operation_filters(store):
    store.append(make_inputs("a" * 32, operation_id="hub.list"))
    store.append(make_inputs("b" * 32, operation_id="hub.aggregate"))
    matching = receipts_for_operation(store.all_documents(), "hub.aggregate")
    assert len(matching) == 1


# ── G14: gates derive only from verified receipts ───────────────────────────

RULES = [
    GateRule("G16_7_OF_7_UI_VALIDATION", "Validation runs through the UI", required_operations=["hub.list"]),
    GateRule("G17_6_OF_6_PRODUCER_EXPORTS", "Producer exports", deferred_reason="out of scope"),
    GateRule("G07_NATIVE_SECRETS", "macOS Keychain certified", blocked_reason="no macOS in CI"),
]


def test_gate_passes_only_with_a_verified_successful_receipt(store, signer):
    store.append(make_inputs("a" * 32, operation_id="hub.list"))
    evidence = evaluate_gates(
        RULES, store.all_documents(), public_key_pem=signer.public_key_pem(), schema=RECEIPT_SCHEMA
    )
    gate = evidence["gates"][0]
    assert gate["status"] == "passed"
    assert len(gate["derived_from"]) == 1
    assert gate["derived_from"][0]["signature_verified"] is True


def test_gate_does_not_pass_without_any_receipt(signer):
    evidence = evaluate_gates(RULES, [], public_key_pem=signer.public_key_pem())
    assert evidence["gates"][0]["status"] == "not_run"
    assert evidence["gates"][0]["derived_from"] == []


def test_a_failed_run_does_not_satisfy_a_gate(store, signer):
    store.append(make_inputs("a" * 32, operation_id="hub.list", status="failed"))
    evidence = evaluate_gates(RULES, store.all_documents(), public_key_pem=signer.public_key_pem())
    assert evidence["gates"][0]["status"] == "not_run"


def test_a_forged_receipt_contributes_nothing(store, signer):
    store.append(make_inputs("a" * 32, operation_id="hub.list"))
    path = store.path_for("a" * 32)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["receipt"]["operation_id"] = "hub.list"
    document["receipt"]["status"] = "succeeded"
    document["signature"]["value"] = "AA" * 32
    path.write_text(json.dumps(document), encoding="utf-8")

    evidence = evaluate_gates(RULES, store.all_documents(), public_key_pem=signer.public_key_pem())
    assert evidence["gates"][0]["status"] == "not_run"


def test_a_receipt_from_an_unknown_key_contributes_nothing(store):
    store.append(make_inputs("a" * 32, operation_id="hub.list"))
    attacker = ReceiptSigner.generate("attacker")
    evidence = evaluate_gates(
        RULES, store.all_documents(), public_key_pem=attacker.public_key_pem()
    )
    assert evidence["gates"][0]["status"] == "not_run"


def test_an_annotation_cannot_turn_a_gate_green(store, signer):
    evidence = evaluate_gates(RULES, [], public_key_pem=signer.public_key_pem())
    assert evidence["gates"][0]["status"] == "not_run"

    annotated = annotate(
        evidence, "G16_7_OF_7_UI_VALIDATION", "operator", "I ran this by hand, it works"
    )

    gate = annotated["gates"][0]
    assert gate["status"] == "not_run", "a note must not change status"
    assert gate["annotations"][0]["note"].startswith("I ran this")


def test_annotations_survive_but_are_ignored_on_re_evaluation(store, signer):
    notes = {"G16_7_OF_7_UI_VALIDATION": [
        {"author": "operator", "note": "passed manually", "recorded_at": "2026-07-27T00:00:00Z"}
    ]}
    evidence = evaluate_gates(
        RULES, [], public_key_pem=signer.public_key_pem(), annotations=notes
    )
    gate = evidence["gates"][0]
    assert gate["status"] == "not_run"
    assert len(gate["annotations"]) == 1


def test_annotating_an_unknown_gate_raises(signer):
    evidence = evaluate_gates(RULES, [], public_key_pem=signer.public_key_pem())
    with pytest.raises(ReceiptError, match="unknown gate"):
        annotate(evidence, "G99_MADE_UP", "operator", "x")


def test_blocked_and_deferred_gates_report_their_reason(signer):
    evidence = evaluate_gates(RULES, [], public_key_pem=signer.public_key_pem())
    by_id = {gate["gate_id"]: gate for gate in evidence["gates"]}
    assert by_id["G07_NATIVE_SECRETS"]["status"] == "blocked_not_certified"
    assert "macOS" in by_id["G07_NATIVE_SECRETS"]["status_reason"]
    assert by_id["G17_6_OF_6_PRODUCER_EXPORTS"]["status"] == "deferred"


def test_gate_evidence_is_schema_valid(store, signer, tmp_path):
    from jsonschema import Draft202012Validator

    from server.backend.federation_manager import RELEASE_FORMAT_CHECKER

    store.append(make_inputs("a" * 32, operation_id="hub.list"))
    evidence = evaluate_gates(
        RULES,
        store.all_documents(),
        public_key_pem=signer.public_key_pem(),
        schema=RECEIPT_SCHEMA,
        policy_sha256="d" * 64,
    )
    Draft202012Validator(GATE_SCHEMA, format_checker=RELEASE_FORMAT_CHECKER).validate(evidence)

    path = write_gate_evidence(tmp_path / "gate_evidence.json", evidence)
    assert json.loads(path.read_text(encoding="utf-8"))["gates"]


def test_schema_forbids_a_passed_gate_with_no_evidence():
    """The invariant is enforced by the schema, not only by the evaluator."""
    from jsonschema import Draft202012Validator, ValidationError

    from server.backend.federation_manager import RELEASE_FORMAT_CHECKER

    forged = {
        "schema_version": "prii_gate_evidence_v1",
        "evaluated_at": "2026-07-27T00:00:00Z",
        "gates": [
            {
                "gate_id": "G16_7_OF_7_UI_VALIDATION",
                "status": "passed",
                "blocking": True,
                "derived_from": [],
            }
        ],
    }
    with pytest.raises(ValidationError):
        Draft202012Validator(GATE_SCHEMA, format_checker=RELEASE_FORMAT_CHECKER).validate(forged)


def test_summarize_counts_statuses(store, signer):
    store.append(make_inputs("a" * 32, operation_id="hub.list"))
    evidence = evaluate_gates(RULES, store.all_documents(), public_key_pem=signer.public_key_pem())
    counts = summarize(evidence)
    assert counts["passed"] == 1
    assert counts["blocked_not_certified"] == 1
    assert counts["deferred"] == 1
