from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import List, Optional

import pytest

from control_plane import (
    EgressPolicyError,
    compute_egress_policy_decision,
    record_egress_decision,
    record_model_run_receipt,
)


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


PROMPT_SHA = _sha(b"vision-template-v1")


def _provider(
    provider_id: str,
    deployment: str,
    classifications: List[str],
    *,
    residencies: List[str],
    credential_references: List[object],
    approval_required_for: Optional[List[str]] = None,
    exact_rules: Optional[List[dict]] = None,
) -> dict:
    return {
        "provider_id": provider_id,
        "deployment": deployment,
        "residencies": residencies,
        "permitted_uses": ["aviation_extraction"],
        "task_types": ["vision_extract.v1"],
        "allowed_classifications": classifications,
        "allowed_models": [
            {"model_id": provider_id + "-vision", "revisions": ["rev-1"]}
        ],
        "allowed_prompt_templates": [
            {"version": "vision-template.v1", "sha256": PROMPT_SHA}
        ],
        "allowed_input_fields": ["image_crop", "artifact_metadata"],
        "required_input_fields": ["image_crop"],
        "approval_required_for": (
            approval_required_for
            if approval_required_for is not None
            else []
        ),
        "credential_references": credential_references,
        "exact_egress_rules": exact_rules or [],
    }


def _policy() -> dict:
    restricted = [
        {
            "classification": level,
            "task_type": "vision_extract.v1",
            "purpose": "aviation_extraction",
            "model_id": "external-vision-vision",
            "model_revision": "rev-1",
        }
        for level in [
            "RESTRICTED",
            "SENSITIVE_LOCATION",
            "LEGAL_HOLD",
            "QUARANTINED",
        ]
    ]
    return {
        "schema_version": "egress_policy.v1",
        "policy_version": "policy-2026-07-30",
        "providers": [
            _provider(
                "external-vision",
                "EXTERNAL",
                [
                    "PUBLIC",
                    "INTERNAL",
                    "RESTRICTED",
                    "SENSITIVE_LOCATION",
                    "LEGAL_HOLD",
                    "QUARANTINED",
                ],
                residencies=["us-east"],
                credential_references=["credential://external-vision"],
                approval_required_for=[
                    "RESTRICTED",
                    "SENSITIVE_LOCATION",
                    "LEGAL_HOLD",
                    "QUARANTINED",
                ],
                exact_rules=restricted,
            ),
            _provider(
                "local-private",
                "LOCAL_PRIVATE",
                [
                    "PUBLIC",
                    "INTERNAL",
                    "RESTRICTED",
                    "SENSITIVE_LOCATION",
                    "LEGAL_HOLD",
                    "QUARANTINED",
                ],
                residencies=["local"],
                credential_references=[None],
            ),
        ],
        "fallbacks": [
            {
                "from_provider_id": "external-vision",
                "task_type": "vision_extract.v1",
                "purpose": "aviation_extraction",
                "classifications": [
                    "PUBLIC",
                    "INTERNAL",
                    "RESTRICTED",
                    "SENSITIVE_LOCATION",
                    "LEGAL_HOLD",
                    "QUARANTINED",
                ],
                "provider_id": "local-private",
                "model_id": "local-private-vision",
                "model_revision": "rev-1",
                "residency": "local",
                "credential_reference": None,
                "priority": 1,
            }
        ],
    }


def _request(
    *,
    classification: str = "PUBLIC",
    restriction_floor: Optional[str] = None,
    snapshot_state: str = "ACTIVE",
) -> dict:
    digest = _sha(b"artifact")
    return {
        "request_id": "request-1",
        "artifact": {
            "artifact_id": "artifact-sha256-" + digest,
            "sha256": digest,
            "snapshot_state": snapshot_state,
            "classification": {
                "level": classification,
                "restriction_floor": restriction_floor or (
                    "PUBLIC" if classification == "TEST_ONLY" else classification
                ),
                "test_only": classification == "TEST_ONLY",
                "lineage_complete": True,
            },
        },
        "task": {
            "task_type": "vision_extract.v1",
            "purpose": "aviation_extraction",
            "input_fields": ["image_crop"],
            "expected_output_fields": ["registration", "aircraft_type"],
        },
        "provider": {
            "provider_id": "external-vision",
            "deployment": "EXTERNAL",
            "residency": "us-east",
            "permitted_use": "aviation_extraction",
            "model_id": "external-vision-vision",
            "model_revision": "rev-1",
            "credential_reference": "credential://external-vision",
        },
        "prompt_template": {
            "version": "vision-template.v1",
            "sha256": PROMPT_SHA,
        },
        "access_context": {
            "workspace_id": "workspace-1",
            "actor_id": "operator-1",
            "roles": ["analyst"],
        },
        "authorization_reference": "authorization-1",
        "audit_event_reference": "audit-1",
        "approval": {
            "state": "APPROVED",
            "approval_reference": "approval-1",
        },
    }


def test_public_external_allowlist_decision_is_pure() -> None:
    policy = _policy()
    request = _request()
    first = compute_egress_policy_decision(policy, request)
    second = compute_egress_policy_decision(policy, request)
    assert first == second
    assert first["decision"] == "ALLOW_EXTERNAL"
    assert first["allowed"] is True
    assert first["selected_provider"]["model_revision"] == "rev-1"
    assert first["accounting"] == {
        "requests": 1,
        "allowed": 1,
        "denied": 0,
        "fallback_selected": 0,
    }


@pytest.mark.parametrize(
    "classification",
    ["RESTRICTED", "SENSITIVE_LOCATION", "LEGAL_HOLD"],
)
def test_high_risk_external_requires_exact_policy(
    classification: str,
) -> None:
    policy = _policy()
    policy["providers"][0]["exact_egress_rules"] = []
    decision = compute_egress_policy_decision(
        policy, _request(classification=classification)
    )
    assert decision["decision"] == "USE_LOCAL_PRIVATE"
    assert "EXACT_CLASSIFICATION_POLICY_MISSING" in decision["reason_codes"]
    assert decision["selected_provider"]["deployment"] == "LOCAL_PRIVATE"


def test_quarantined_non_active_artifact_is_denied_even_with_exact_policy() -> None:
    decision = compute_egress_policy_decision(
        _policy(),
        _request(classification="QUARANTINED", snapshot_state="QUARANTINED"),
    )
    assert decision["decision"] == "DENIED"
    assert "NON_ACTIVE_ARTIFACT_DENIED" in decision["reason_codes"]


def test_test_only_external_egress_is_denied_or_local_fallback() -> None:
    policy = _policy()
    request = _request(classification="TEST_ONLY", restriction_floor="PUBLIC")
    decision = compute_egress_policy_decision(policy, request)
    assert decision["decision"] == "USE_LOCAL_PRIVATE"
    assert "TEST_ONLY_EXTERNAL_EGRESS_DENIED" in decision["reason_codes"]
    assert decision["selected_provider"]["deployment"] == "LOCAL_PRIVATE"


def test_residency_purpose_approval_and_minimization_fail_closed() -> None:
    request = _request(classification="RESTRICTED")
    request["provider"]["residency"] = "eu-west"
    request["task"]["purpose"] = "unapproved_purpose"
    request["provider"]["permitted_use"] = "unapproved_purpose"
    request["approval"] = {"state": "PENDING"}
    request["task"]["input_fields"] = ["image_crop", "raw_case_file"]
    decision = compute_egress_policy_decision(_policy(), request)
    assert decision["decision"] == "DENIED"
    assert {
        "PROVIDER_RESIDENCY_MISMATCH",
        "PURPOSE_NOT_PERMITTED",
        "APPROVAL_REQUIRED",
        "DATA_MINIMIZATION_REQUIRED",
    } <= set(decision["reason_codes"])


def test_no_provider_or_model_default_is_used() -> None:
    request = _request()
    request["provider"]["provider_id"] = ""
    request["provider"]["model_id"] = ""
    request["provider"]["model_revision"] = ""
    decision = compute_egress_policy_decision(_policy(), request)
    assert decision["decision"] == "DENIED"
    assert "PROVIDER_NOT_ALLOWLISTED" in decision["reason_codes"]


def test_decision_receipt_replay_and_secret_nonserialization(
    tmp_path: Path,
) -> None:
    policy = _policy()
    request = _request()
    receipt = record_egress_decision(
        tmp_path,
        "decision-run-1",
        policy,
        request,
        completed_at="2026-07-30T21:10:00Z",
    )
    replay = record_egress_decision(
        tmp_path,
        "decision-run-1",
        policy,
        request,
        completed_at="later-is-ignored",
    )
    assert replay == receipt
    serialized = json.dumps(receipt)
    assert "credential://external-vision" in serialized
    assert "actual-secret-value" not in serialized
    assert receipt["secret_material_serialized"] is False

    changed = copy.deepcopy(request)
    changed["task"]["purpose"] = "changed"
    with pytest.raises(EgressPolicyError, match="different policy or request"):
        record_egress_decision(
            tmp_path,
            "decision-run-1",
            policy,
            changed,
            completed_at="2026-07-30T21:11:00Z",
        )


def test_secret_material_is_typed_fail_closed() -> None:
    request = _request()
    request["provider"]["api_key"] = "actual-secret-value"
    decision = compute_egress_policy_decision(_policy(), request)
    assert decision["decision"] == "DENIED"
    assert "SECRET_MATERIAL_PRESENT" in decision["reason_codes"]
    assert "actual-secret-value" not in json.dumps(decision)


def test_model_run_receipt_has_complete_field_provenance_and_accounting(
    tmp_path: Path,
) -> None:
    egress = record_egress_decision(
        tmp_path,
        "decision-run-model",
        _policy(),
        _request(),
        completed_at="2026-07-30T21:12:00Z",
    )
    receipt = record_model_run_receipt(
        tmp_path,
        "model-run-1",
        egress,
        [
            {
                "field_name": "registration",
                "value": "N999ZY",
                "confidence": 0.91,
                "validation_outcome": "UNVERIFIED",
                "review_status": "NEEDS_REVIEW",
                "reviewer_id": None,
                "created_at": "2026-07-30T21:13:00Z",
                "source_region": {"x": 1, "y": 2, "width": 3, "height": 4},
            }
        ],
        [
            {
                "field_name": "aircraft_type",
                "failure_code": "NOT_VISIBLE",
            }
        ],
        extraction_schema_version="aviation_extract.v1",
        completed_at="2026-07-30T21:13:01Z",
    )
    assert receipt["outcome"] == "PARTIAL"
    assert receipt["accounting"] == {
        "expected_fields": 2,
        "output_fields": 1,
        "failed_fields": 1,
    }
    assert receipt["model_execution_performed_by_this_module"] is False
    ref = receipt["field_provenance"][0]
    field_record = json.loads((tmp_path / ref["locator"]).read_text())
    assert field_record["source_artifact_id"] == egress["artifact"]["artifact_id"]
    assert field_record["model_run_receipt_id"] == receipt["model_run_receipt_id"]
    assert field_record["provider"] == "external-vision"
    assert field_record["model"] == "external-vision-vision"
    assert field_record["model_revision"] == "rev-1"
    assert field_record["prompt_template_version"] == "vision-template.v1"
    assert field_record["prompt_hash"] == PROMPT_SHA
    assert field_record["policy_version"] == _policy()["policy_version"]
    assert field_record["access_context_hash"] == egress[
        "access_context_sha256"
    ]
    assert field_record["extraction_schema_version"] == "aviation_extract.v1"


def test_model_run_receipt_replay_and_changed_output_conflict(
    tmp_path: Path,
) -> None:
    egress = record_egress_decision(
        tmp_path,
        "decision-run-replay",
        _policy(),
        _request(),
        completed_at="2026-07-30T21:14:00Z",
    )
    fields = [
        {
            "field_name": "registration",
            "value": "N999ZY",
            "confidence": 0.9,
            "validation_outcome": "VALID",
            "review_status": "APPROVED",
            "reviewer_id": "reviewer-1",
            "created_at": "2026-07-30T21:14:01Z",
        },
        {
            "field_name": "aircraft_type",
            "value": "unknown",
            "confidence": None,
            "validation_outcome": "UNVERIFIED",
            "review_status": "NEEDS_REVIEW",
            "reviewer_id": None,
            "created_at": "2026-07-30T21:14:01Z",
        },
    ]
    first = record_model_run_receipt(
        tmp_path,
        "model-run-replay",
        egress,
        fields,
        [],
        extraction_schema_version="aviation_extract.v1",
        completed_at="2026-07-30T21:14:02Z",
    )
    replay = record_model_run_receipt(
        tmp_path,
        "model-run-replay",
        egress,
        fields,
        [],
        extraction_schema_version="aviation_extract.v1",
        completed_at="ignored",
    )
    assert replay == first
    changed = copy.deepcopy(fields)
    changed[0]["value"] = "N00000"
    with pytest.raises(EgressPolicyError, match="different inputs or outputs"):
        record_model_run_receipt(
            tmp_path,
            "model-run-replay",
            egress,
            changed,
            [],
            extraction_schema_version="aviation_extract.v1",
            completed_at="2026-07-30T21:15:00Z",
        )


def test_non_active_artifact_cannot_enter_model_context(tmp_path: Path) -> None:
    egress = record_egress_decision(
        tmp_path,
        "denied-non-active",
        _policy(),
        _request(snapshot_state="CERTIFIED"),
        completed_at="2026-07-30T21:16:00Z",
    )
    assert egress["allowed"] is False
    with pytest.raises(EgressPolicyError, match="denied egress decision"):
        record_model_run_receipt(
            tmp_path,
            "model-non-active",
            egress,
            [],
            [],
            extraction_schema_version="aviation_extract.v1",
            completed_at="2026-07-30T21:16:01Z",
        )


def test_static_boundary_has_no_provider_model_rpc_database_or_query_runtime() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "control_plane"
    source = (
        (root / "_egress_common.py").read_text()
        + (root / "_egress_rules.py").read_text()
        + (root / "egress_policy.py").read_text()
        + (root / "model_run_receipt.py").read_text()
    ).lower()
    forbidden = (
        "import requests",
        "from requests",
        "import httpx",
        "from httpx",
        "urllib.request",
        "anthropic",
        "openai",
        "boto3",
        "google.generativeai",
        "skywatcher",
        "import subprocess",
        "import sqlalchemy",
        "import psycopg",
        "database_url",
        "execute_model",
        "answer_query",
        "query_runtime",
    )
    assert all(token not in source for token in forbidden)
