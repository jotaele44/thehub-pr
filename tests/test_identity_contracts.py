from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

CONTRACTS = (
    "federation_entity.v1.schema.json",
    "federation_entity_member.v1.schema.json",
    "federation_alias.v1.schema.json",
    "federation_identifier.v1.schema.json",
    "federation_relationship.v1.schema.json",
    "federation_provenance.v1.schema.json",
    "federation_event.v1.schema.json",
    "entity_resolution.v1.schema.json",
)


def test_identity_contracts_are_valid_draft_2020_12_schemas():
    root = Path("schemas/contracts")
    for name in CONTRACTS:
        schema = json.loads((root / name).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)


def test_member_contract_reuses_entity_resolution_decision_id():
    schema = json.loads(Path("schemas/contracts/federation_entity_member.v1.schema.json").read_text())
    assert "decision_id" in schema["required"]
    assert "reason_code" not in schema["required"]
    assert "evidence_ids" not in schema["required"]


def test_event_contract_contains_all_fail_closed_dispositions():
    schema = json.loads(Path("schemas/contracts/federation_event.v1.schema.json").read_text())
    assert set(schema["properties"]["disposition"]["enum"]) == {
        "APPLIED", "IDEMPOTENT_REPLAY", "REJECTED_STALE", "REJECTED_OUT_OF_ORDER",
        "REJECTED_SCHEMA", "REJECTED_HASH", "REJECTED_AUTHORITY", "REJECTED_INVARIANT",
    }
