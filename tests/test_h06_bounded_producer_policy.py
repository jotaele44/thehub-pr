from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from h06_support import _canonical_bytes, _decision, _h05_receipt, _job, _resign

def test_v2_job_contract_accepts_signed_pinned_job() -> None:
    schema_dir = (
        Path(__file__).resolve().parents[1]
        / "schemas"
        / "contracts"
        / "skywatcher_ai"
    )
    schemas = {
        name: json.loads((schema_dir / name).read_text())
        for name in (
            "skywatcher_ai_common.v1.schema.json",
            "bounded_producer_job.v2.schema.json",
        )
    }
    registry = Registry()
    for name, schema in schemas.items():
        resource = Resource.from_contents(schema)
        registry = registry.with_resource(name, resource)
        registry = registry.with_resource(schema["$id"], resource)
    validator = Draft202012Validator(
        schemas["bounded_producer_job.v2.schema.json"], registry=registry
    )
    assert list(validator.iter_errors(_job())) == []

def test_valid_offline_job_is_accepted_without_execution() -> None:
    decision = _decision(_job())
    assert decision["accepted"] is True
    assert decision["decision"] == "ACCEPTED"
    assert decision["signature"]["verified"] is True
    assert decision["authorization_verified"] is True
    assert decision["worker_execution_performed"] is False
    assert decision["network_policy"]["default"] == "DENY"


def test_unknown_job_field_is_denied() -> None:
    job = _job()
    job["ignored_policy_bypass"] = True
    _resign(job)
    assert "JOB_SPEC_FIELDS_INVALID" in _decision(job)["reason_codes"]


def test_unsigned_job_is_denied() -> None:
    job = _job()
    job.pop("signature")
    decision = _decision(job)
    assert decision["accepted"] is False
    assert "JOB_SPEC_SIGNATURE_REQUIRED" in decision["reason_codes"]


def test_signature_mismatch_is_denied() -> None:
    job = _job()
    job["signature"]["value"] = "0" * 64
    decision = _decision(job)
    assert "JOB_SPEC_SIGNATURE_MISMATCH" in decision["reason_codes"]


def test_revision_and_schema_drift_are_denied() -> None:
    job = _job()
    job["producer_revision"] = "9" * 40
    job["pins"]["schema_revisions"]["aviation_extract"] = "drifted.v2"
    _resign(job)
    decision = _decision(job)
    assert {"PRODUCER_REVISION_DRIFT", "SCHEMA_REVISION_DRIFT"} <= set(
        decision["reason_codes"]
    )


def test_non_content_addressed_input_is_denied() -> None:
    job = _job()
    job["input_artifacts"][0]["read_only_locator"] = "/tmp/input.png"
    _resign(job)
    assert "INPUT_NOT_CONTENT_ADDRESSED" in _decision(job)["reason_codes"]


def test_non_active_input_requires_explicit_provisional_workflow() -> None:
    job = _job(snapshot_state="QUARANTINED")
    assert _decision(job)["accepted"] is True
    job["workflow_mode"] = "ACTIVE_EVIDENCE"
    _resign(job)
    assert "NON_ACTIVE_INPUT_DENIED" in _decision(job)["reason_codes"]


def test_unauthorized_network_request_is_denied() -> None:
    job = _job()
    job["capabilities"]["network_access"] = True
    job["network_policy"]["approved_hosts"] = ["example.invalid"]
    job["network_policy"]["max_requests"] = 1
    _resign(job)
    decision = _decision(job)
    assert {"NETWORK_EXCEPTION_UNAUTHORIZED", "H05_EGRESS_RECEIPT_REQUIRED"} <= set(
        decision["reason_codes"]
    )


def test_model_operation_requires_h05_receipt() -> None:
    job = _job()
    job["capabilities"]["model_operation"] = True
    _resign(job)
    assert "H05_EGRESS_RECEIPT_REQUIRED" in _decision(job)["reason_codes"]


def test_authorized_network_exception_is_bound_to_h05_receipt() -> None:
    job = _job()
    job["capabilities"]["network_access"] = True
    job["network_policy"].update(
        {
            "approved_hosts": ["imagery.example.test"],
            "max_requests": 2,
            "exception_authorization_reference": "authorization-h06-1",
        }
    )
    receipt = _h05_receipt(job)
    job["h05_egress_reference"] = {
        "decision_receipt_id": receipt["decision_receipt_id"],
        "sha256": hashlib.sha256(_canonical_bytes(receipt)).hexdigest(),
    }
    _resign(job)
    decision = _decision(job, receipt)
    assert decision["accepted"] is True
    assert decision["egress_verified"] is True


def test_database_mount_is_denied() -> None:
    job = _job()
    job["workspace_policy"]["database_mounts"] = ["skywatcher.sqlite"]
    _resign(job)
    assert "DATABASE_MOUNT_DENIED" in _decision(job)["reason_codes"]


def test_secret_reference_is_allowed_but_secret_value_is_denied() -> None:
    job = _job()
    assert _decision(job)["accepted"] is True
    job["credential_value"] = "actual-secret"
    _resign(job)
    decision = _decision(job)
    assert "SECRET_VALUE_PRESENT" in decision["reason_codes"]
    assert "actual-secret" not in json.dumps(decision)
