from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from research.drought.situation_projection import (
    assert_zero_duplicate_ingest,
    build_situation_projection,
)

ROOT = Path(__file__).resolve().parents[1]


def test_schema_is_valid() -> None:
    schema = json.loads((ROOT / "schemas/drought-situation-v0.1.schema.json").read_text())
    Draft202012Validator.check_schema(schema)


def test_projection_contains_references_only() -> None:
    projection = build_situation_projection(
        area_id="PR",
        valid_at="2026-07-21T17:00:00-04:00",
        aguayluz_records=[
            {
                "record_id": "AYL_DROUGHT_CLASSIFICATION_OBSERVATION_0123456789abcdef0123",
                "kind": "classification_observation",
                "content_sha256": "a" * 64,
                "quality": {"freshness": "historical_snapshot"},
                "evidence_tier": "T1",
            }
        ],
        centinelas_events=[
            {
                "event_id": "CEN_DROUGHT_0123456789abcdef0123",
                "impact_type": "wildfire_activity",
                "content_sha256": "b" * 64,
                "evidence_tier": "T2",
                "canonical_hydrology_embedded": False,
            }
        ],
    )
    assert projection["read_only"] is True
    assert projection["independent_ingest"] is False
    assert projection["canonical_hydrology_embedded"] is False
    assert_zero_duplicate_ingest(projection)


def test_noncanonical_producer_ids_fail_closed() -> None:
    with pytest.raises(ValueError, match="AguaYLuz"):
        build_situation_projection(
            area_id="PR",
            valid_at="2026-07-21T17:00:00-04:00",
            aguayluz_records=[{"record_id": "copied-record"}],
            centinelas_events=[],
        )


def test_embedded_hydrology_is_rejected() -> None:
    with pytest.raises(ValueError, match="embed canonical hydrology"):
        build_situation_projection(
            area_id="PR",
            valid_at="2026-07-21T17:00:00-04:00",
            aguayluz_records=[],
            centinelas_events=[
                {
                    "event_id": "CEN_DROUGHT_0123456789abcdef0123",
                    "canonical_hydrology_embedded": True,
                }
            ],
        )
    with pytest.raises(ValueError, match="duplicate canonical fields"):
        assert_zero_duplicate_ingest(
            {
                "independent_ingest": False,
                "canonical_hydrology_embedded": False,
                "streamflow_value": 25,
            }
        )
