"""Contract-only tests for ADR 0006 Skywatcher AI/imagery schemas."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas" / "contracts" / "skywatcher_ai"


def _schemas() -> dict[str, dict]:
    return {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(SCHEMA_DIR.glob("*.json"))
    }


def _registry(schemas: dict[str, dict]) -> Registry:
    registry = Registry()
    for name, schema in schemas.items():
        registry = registry.with_resource(name, Resource.from_contents(schema))
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    return registry


def test_all_contracts_are_valid_draft_2020_12() -> None:
    schemas = _schemas()
    assert len(schemas) == 18
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)


def test_all_local_references_resolve() -> None:
    schemas = _schemas()
    registry = _registry(schemas)
    for schema in schemas.values():
        Draft202012Validator(schema, registry=registry).check_schema(schema)


def test_bounded_job_is_network_denied_and_database_isolated() -> None:
    schemas = _schemas()
    registry = _registry(schemas)
    schema = schemas["bounded_producer_job.v1.schema.json"]
    valid = {
        "schema_version": "bounded_producer_job.v1",
        "job_id": "job-1",
        "producer": "skywatcher-pr",
        "producer_revision": "a" * 40,
        "operation_id": "extract-fr24",
        "signed_command_policy_id": "policy-1",
        "input_artifacts": [{
            "artifact_id": "artifact-1",
            "sha256": "b" * 64,
            "read_only_locator": "cas://sha256/b",
            "classification": "INTERNAL",
        }],
        "output_contract": {"schema_id": "skywatcher.producer_package.v2", "write_root": "/output"},
        "workspace_policy": {
            "ephemeral": True,
            "persistent_db_mounts": False,
            "evidence_db_access": False,
            "secret_readback": False,
        },
        "network_policy": {"default": "DENY", "approved_hosts": [], "max_requests": 0},
        "requested_by": "operator-1",
        "created_at": "2026-07-29T23:00:00-04:00",
    }
    validator = Draft202012Validator(schema, registry=registry)
    assert list(validator.iter_errors(valid)) == []
    invalid = json.loads(json.dumps(valid))
    invalid["network_policy"]["default"] = "ALLOW"
    assert list(validator.iter_errors(invalid))


def test_model_field_requires_real_engine_provenance() -> None:
    schemas = _schemas()
    registry = _registry(schemas)
    schema = schemas["model_field_provenance.v1.schema.json"]
    incomplete = {
        "schema_version": "model_field_provenance.v1",
        "field_id": "field-1",
        "source_artifact_id": "artifact-1",
        "source_sha256": "c" * 64,
        "field_name": "registration",
        "value": "N12345",
        "confidence": 0.9,
        "validation_outcome": "VALID",
        "review_status": "UNREVIEWED",
        "created_at": "2026-07-29T23:00:00-04:00",
    }
    errors = list(Draft202012Validator(schema, registry=registry).iter_errors(incomplete))
    missing = {error.message for error in errors}
    assert any("provider" in message for message in missing)
    assert any("model_run_receipt_id" in message for message in missing)
    assert any("prompt_hash" in message for message in missing)


def test_satim_signal_is_always_provisional() -> None:
    schemas = _schemas()
    registry = _registry(schemas)
    schema = schemas["satim_provisional_signal.v1.schema.json"]
    signal = {
        "schema_version": "satim_provisional_signal.v1",
        "signal_id": "signal-1",
        "source_artifact_ids": ["artifact-1", "artifact-2"],
        "method": "PIXEL_DIFFERENCE",
        "method_version": "1.0.0",
        "parameters": {},
        "result": {"changed_fraction": 0.12},
        "confidence": 0.7,
        "provisional": False,
        "review_status": "NEEDS_REVIEW",
        "created_at": "2026-07-29T23:00:00-04:00",
    }
    errors = list(Draft202012Validator(schema, registry=registry).iter_errors(signal))
    assert any("True was expected" in error.message for error in errors)


def test_phase1_contract_compatibility_when_present() -> None:
    phase1_dir = SCHEMA_DIR.parent
    access_path = phase1_dir / "access_classification.v1.schema.json"
    provider_path = phase1_dir / "provider_reference.v1.schema.json"
    analytical_path = phase1_dir / "analytical_run_receipt.v1.schema.json"
    if not all(path.exists() for path in (access_path, provider_path, analytical_path)):
        pytest.skip("Phase-1 contract namespace is not present on this branch")

    schemas = _schemas()
    common = schemas["skywatcher_ai_common.v1.schema.json"]
    access = json.loads(access_path.read_text(encoding="utf-8"))
    provider = json.loads(provider_path.read_text(encoding="utf-8"))
    analytical = json.loads(analytical_path.read_text(encoding="utf-8"))

    assert common["$defs"]["classification"]["enum"] == access["properties"]["level"]["enum"]
    assert set(provider["required"]) == {"provider", "model"}
    model_fields = schemas["model_field_provenance.v1.schema.json"]["required"]
    assert {"provider", "model", "model_revision", "model_run_receipt_id"} <= set(model_fields)
    assert analytical["properties"]["access_context"]["$ref"].endswith("/access_classification/v1")
