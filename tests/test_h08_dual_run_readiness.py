from __future__ import annotations

import copy
from pathlib import Path

import pytest

from control_plane._dual_run_equivalence import compare_values
from control_plane._dual_run_identity import compute_campaign_id
from control_plane.dual_run_readiness import (
    DualRunReadinessError,
    compute_dual_run_pair_comparison,
    record_dual_run_readiness,
    validate_dual_run_records,
)
from h08_support import NOW, valid_bundle

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas" / "contracts" / "skywatcher_ai"


def _record(tmp_path: Path, camp, policy, lanes, rollback):
    return record_dual_run_readiness(
        tmp_path, camp, policy, lanes, rollback, completed_at=NOW, schema_dir=SCHEMA_DIR
    )


def test_valid_two_pair_campaign_passes_dual_run_gate(tmp_path: Path) -> None:
    camp, policy, lanes, rollback = valid_bundle()
    receipt = _record(tmp_path, camp, policy, lanes, rollback)
    assert receipt["trial_count"] == 2
    assert receipt["dual_run_gate_status"] == "passed"
    assert receipt["rollback_gate_status"] == "passed"
    assert receipt["overall_status"] == "READY_FOR_RETIREMENT_REVIEW"
    assert receipt["retirement_authorized"] is False
    assert receipt["certified_state_created"] is False
    assert receipt["active_snapshot_promoted"] is False
    assert receipt["gate_evidence"]["gates"][1]["status"] == "deferred"


def test_single_pair_denied() -> None:
    camp, policy, lanes, rollback = valid_bundle()
    camp["trials"] = camp["trials"][:1]
    camp["campaign_id"] = compute_campaign_id(camp)
    lanes = lanes[:2]
    for lane in lanes:
        lane["campaign_id"] = camp["campaign_id"]
    rollback["campaign_id"] = camp["campaign_id"]
    with pytest.raises(DualRunReadinessError, match="too short|at least two"):
        validate_dual_run_records(camp, policy, lanes, rollback, schema_dir=SCHEMA_DIR)


def test_duplicated_execution_receipt_denied() -> None:
    camp, policy, lanes, rollback = valid_bundle()
    lanes[1]["execution_receipt"] = copy.deepcopy(lanes[0]["execution_receipt"])
    with pytest.raises(DualRunReadinessError, match="duplicated execution"):
        validate_dual_run_records(camp, policy, lanes, rollback, schema_dir=SCHEMA_DIR)


def test_duplicated_execution_receipt_sha_denied() -> None:
    camp, policy, lanes, rollback = valid_bundle()
    lanes[1]["execution_receipt"]["receipt_sha256"] = lanes[0][
        "execution_receipt"
    ]["receipt_sha256"]
    with pytest.raises(DualRunReadinessError, match="duplicated execution"):
        validate_dual_run_records(camp, policy, lanes, rollback, schema_dir=SCHEMA_DIR)


def test_source_set_drift_denied() -> None:
    camp, policy, lanes, rollback = valid_bundle()
    lanes[0]["source_set_sha256"] = "0" * 64
    with pytest.raises(DualRunReadinessError, match="source set drift"):
        validate_dual_run_records(camp, policy, lanes, rollback, schema_dir=SCHEMA_DIR)


def test_revision_or_pin_drift_denied() -> None:
    camp, policy, lanes, rollback = valid_bundle()
    lanes[0]["pins_sha256"] = "0" * 64
    with pytest.raises(DualRunReadinessError, match="pin-set drift"):
        validate_dual_run_records(camp, policy, lanes, rollback, schema_dir=SCHEMA_DIR)


def test_campaign_revision_drift_breaks_identity() -> None:
    camp, policy, lanes, rollback = valid_bundle()
    camp["skywatcher_revision"] = "4" * 40
    with pytest.raises(DualRunReadinessError, match="campaign_id"):
        validate_dual_run_records(camp, policy, lanes, rollback, schema_dir=SCHEMA_DIR)


def test_deterministic_output_set_mismatch_denied() -> None:
    camp, policy, lanes, _rollback = valid_bundle()
    candidate = lanes[1]
    candidate["deterministic_outputs"].pop()
    comparison = compute_dual_run_pair_comparison(
        camp, policy, lanes[0], candidate, completed_at=NOW
    )
    assert comparison["outcome"] == "NON_EQUIVALENT"
    assert comparison["deterministic_accounting"]["MISSING"] == 1


def test_deterministic_digest_mismatch_denied() -> None:
    camp, policy, lanes, _rollback = valid_bundle()
    lanes[1]["deterministic_outputs"][0]["normalized_sha256"] = "0" * 64
    comparison = compute_dual_run_pair_comparison(
        camp, policy, lanes[0], lanes[1], completed_at=NOW
    )
    assert comparison["deterministic_accounting"]["UNEQUAL"] == 1
    assert comparison["outcome"] == "NON_EQUIVALENT"


def test_model_field_exact_and_versioned_comparators_accept() -> None:
    camp, policy, lanes, _rollback = valid_bundle()
    comparison = compute_dual_run_pair_comparison(
        camp, policy, lanes[0], lanes[1], completed_at=NOW
    )
    assert comparison["model_field_accounting"]["EQUIVALENT"] == len(
        camp["required_model_fields"]
    )
    assert comparison["outcome"] == "EQUIVALENT"


def test_relative_numeric_comparator() -> None:
    ok, detail = compare_values(
        100.0,
        101.0,
        {
            "comparator": "NUMERIC_RELATIVE_TOLERANCE",
            "parameters": {"tolerance": 0.01},
        },
    )
    assert ok is True
    assert detail["relative_delta"] <= 0.01


def test_enum_comparator() -> None:
    assert compare_values(
        "A", "A", {"comparator": "ENUM_EXACT", "parameters": {}}
    )[0]
    assert not compare_values(
        "A", "B", {"comparator": "ENUM_EXACT", "parameters": {}}
    )[0]


def test_wildcard_or_ignore_rule_denied() -> None:
    camp, policy, lanes, rollback = valid_bundle()
    policy["rules"][0]["field_key"] = "*"
    with pytest.raises(DualRunReadinessError):
        validate_dual_run_records(camp, policy, lanes, rollback, schema_dir=SCHEMA_DIR)


def test_missing_model_field_denied() -> None:
    camp, policy, lanes, _rollback = valid_bundle()
    lanes[1]["model_fields"].pop()
    comparison = compute_dual_run_pair_comparison(
        camp, policy, lanes[0], lanes[1], completed_at=NOW
    )
    assert comparison["model_field_accounting"]["MISSING"] == 1


def test_additional_model_field_denied() -> None:
    camp, policy, lanes, _rollback = valid_bundle()
    extra = copy.deepcopy(lanes[1]["model_fields"][0])
    extra["field_key"] = "unexpected"
    lanes[1]["model_fields"].append(extra)
    comparison = compute_dual_run_pair_comparison(
        camp, policy, lanes[0], lanes[1], completed_at=NOW
    )
    assert comparison["model_field_accounting"]["ADDITIONAL"] == 1


def test_duplicate_model_field_denied() -> None:
    camp, policy, lanes, _rollback = valid_bundle()
    lanes[1]["model_fields"].append(copy.deepcopy(lanes[1]["model_fields"][0]))
    with pytest.raises(DualRunReadinessError, match="duplicate model field"):
        compute_dual_run_pair_comparison(
            camp, policy, lanes[0], lanes[1], completed_at=NOW
        )


def test_model_provenance_drift_denied() -> None:
    camp, policy, lanes, _rollback = valid_bundle()
    lanes[1]["model_fields"][0]["provenance"]["model_revision"] = "drifted"
    comparison = compute_dual_run_pair_comparison(
        camp, policy, lanes[0], lanes[1], completed_at=NOW
    )
    assert comparison["outcome"] == "NON_EQUIVALENT"


def test_unresolved_review_blocks() -> None:
    camp, policy, lanes, _rollback = valid_bundle()
    lanes[1]["model_fields"][0]["review_status"] = "UNRESOLVED_REVIEW"
    comparison = compute_dual_run_pair_comparison(
        camp, policy, lanes[0], lanes[1], completed_at=NOW
    )
    assert comparison["model_field_accounting"]["UNRESOLVED"] == 1


def test_schema_violation_blocks() -> None:
    camp, policy, lanes, rollback = valid_bundle()
    lanes[0]["schema_violations"] = 1
    with pytest.raises(DualRunReadinessError, match="schema violations"):
        validate_dual_run_records(camp, policy, lanes, rollback, schema_dir=SCHEMA_DIR)


def test_missing_provenance_blocks() -> None:
    camp, policy, lanes, rollback = valid_bundle()
    lanes[0]["missing_required_provenance"] = 1
    with pytest.raises(DualRunReadinessError, match="missing required provenance"):
        validate_dual_run_records(camp, policy, lanes, rollback, schema_dir=SCHEMA_DIR)


def test_incomplete_input_accounting_blocks() -> None:
    camp, policy, lanes, rollback = valid_bundle()
    lanes[0]["input_accounting"]["processed"] = 1
    with pytest.raises(DualRunReadinessError, match="input accounting"):
        validate_dual_run_records(camp, policy, lanes, rollback, schema_dir=SCHEMA_DIR)


def test_input_accounting_must_match_campaign_source_set() -> None:
    camp, policy, lanes, rollback = valid_bundle()
    lanes[0]["input_accounting"] = {
        "inputs": 1,
        "processed": 1,
        "excluded": 0,
        "failed": 0,
    }
    with pytest.raises(DualRunReadinessError, match="campaign source set"):
        validate_dual_run_records(camp, policy, lanes, rollback, schema_dir=SCHEMA_DIR)


def test_incomplete_output_accounting_blocks() -> None:
    camp, policy, lanes, rollback = valid_bundle()
    lanes[0]["output_accounting"]["produced"] = 1
    with pytest.raises(DualRunReadinessError, match="output accounting"):
        validate_dual_run_records(camp, policy, lanes, rollback, schema_dir=SCHEMA_DIR)


def test_output_accounting_must_match_campaign_required_outputs() -> None:
    camp, policy, lanes, rollback = valid_bundle()
    lanes[0]["deterministic_outputs"].pop()
    lanes[0]["output_accounting"] = {"required": 1, "produced": 1, "failed": 0}
    with pytest.raises(DualRunReadinessError, match="campaign required outputs"):
        validate_dual_run_records(camp, policy, lanes, rollback, schema_dir=SCHEMA_DIR)


def test_produced_output_accounting_must_match_output_records() -> None:
    camp, policy, lanes, rollback = valid_bundle()
    lanes[0]["output_accounting"] = {"required": 2, "produced": 1, "failed": 1}
    with pytest.raises(DualRunReadinessError, match="output records"):
        validate_dual_run_records(camp, policy, lanes, rollback, schema_dir=SCHEMA_DIR)


def test_valid_rollback_evidence_accepted() -> None:
    camp, policy, lanes, rollback = valid_bundle()
    validate_dual_run_records(camp, policy, lanes, rollback, schema_dir=SCHEMA_DIR)


def test_failed_or_unsigned_rollback_blocks() -> None:
    camp, policy, lanes, rollback = valid_bundle()
    rollback["execution_receipt"]["signature_verified"] = False
    rollback["execution_receipt"]["rollback_state"] = "failed"
    with pytest.raises(DualRunReadinessError, match="verified receipt or attestation"):
        validate_dual_run_records(camp, policy, lanes, rollback, schema_dir=SCHEMA_DIR)


def test_signed_attestation_can_support_rollback() -> None:
    camp, policy, lanes, rollback = valid_bundle()
    rollback["execution_receipt"]["signature_verified"] = False
    rollback["execution_receipt"]["rollback_state"] = "failed"
    rollback["attestations"] = [
        {
            "attestation_id": "operator.rollback",
            "attestation_sha256": "a" * 64,
            "signature_verified": True,
            "result": "satisfied",
        }
    ]
    validate_dual_run_records(camp, policy, lanes, rollback, schema_dir=SCHEMA_DIR)


def test_unexpected_rollback_writes_block() -> None:
    camp, policy, lanes, rollback = valid_bundle()
    rollback["unexpected_writes"] = ["outside/managed/root"]
    with pytest.raises(DualRunReadinessError, match="unexpected rollback writes"):
        validate_dual_run_records(camp, policy, lanes, rollback, schema_dir=SCHEMA_DIR)


def test_exact_replay_is_idempotent(tmp_path: Path) -> None:
    camp, policy, lanes, rollback = valid_bundle()
    first = _record(tmp_path, camp, policy, lanes, rollback)
    second = _record(tmp_path, camp, policy, lanes, rollback)
    assert first == second


def test_changed_evidence_replay_conflicts(tmp_path: Path) -> None:
    camp, policy, lanes, rollback = valid_bundle()
    _record(tmp_path, camp, policy, lanes, rollback)
    changed = copy.deepcopy(lanes)
    changed[0]["model_fields"][0]["value"] = "N99999"
    with pytest.raises(DualRunReadinessError, match="changed campaign"):
        _record(tmp_path, camp, policy, changed, rollback)


def test_static_boundary_has_no_prohibited_runtime() -> None:
    module_root = Path(__file__).resolve().parents[1] / "src" / "control_plane"
    source = "\n".join(
        (module_root / name).read_text(encoding="utf-8")
        for name in (
            "_dual_run_common.py",
            "_dual_run_identity.py",
            "_dual_run_equivalence.py",
            "_dual_run_validation.py",
            "_dual_run_receipts.py",
            "dual_run_readiness.py",
        )
    ).lower()
    forbidden = (
        "import subprocess",
        "from subprocess",
        "docker",
        "kubernetes",
        "import requests",
        "from requests",
        "import httpx",
        "from httpx",
        "urllib.request",
        "boto3",
        "anthropic",
        "openai",
        "import sqlalchemy",
        "import psycopg",
        "database_url",
        "launch_worker",
        "execute_model",
        "answer_query",
        "retrieval_engine",
        "promote_snapshot",
        "certify_evidence",
    )
    assert all(token not in source for token in forbidden)
