from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas" / "contracts" / "skywatcher_ai"
H08 = {
    "dual_run_campaign_manifest.v1.schema.json",
    "model_field_equivalence_policy.v1.schema.json",
    "dual_run_lane_evidence.v1.schema.json",
    "dual_run_comparison_receipt.v1.schema.json",
    "dual_run_readiness_receipt.v1.schema.json",
    "rollback_drill_evidence.v1.schema.json",
}


def test_h08_contracts_are_draft_2020_12() -> None:
    assert H08 <= {path.name for path in SCHEMA_DIR.glob("*.json")}
    for name in H08:
        schema = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        assert schema["$schema"].endswith("2020-12/schema")


def test_h08_contracts_prohibit_retirement_and_promotion() -> None:
    campaign = json.loads((SCHEMA_DIR / "dual_run_campaign_manifest.v1.schema.json").read_text())
    readiness = json.loads((SCHEMA_DIR / "dual_run_readiness_receipt.v1.schema.json").read_text())
    assert campaign["properties"]["retirement_authorized"] == {"const": False}
    assert campaign["properties"]["production_mutation_allowed"] == {"const": False}
    assert readiness["properties"]["retirement_authorized"] == {"const": False}
    assert readiness["properties"]["certified_state_created"] == {"const": False}
    assert readiness["properties"]["active_snapshot_promoted"] == {"const": False}
