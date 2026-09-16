from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from research.drought.situation_projection import (
    assert_zero_duplicate_ingest,
    build_situation_projection,
)

ROOT = Path(__file__).resolve().parents[1]


def test_schema_is_valid() -> None:
    schema = json.loads(
        (ROOT / "schemas/drought-situation-v0.1.schema.json").read_text()
    )
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
    schema = json.loads(
        (ROOT / "schemas/drought-situation-v0.1.schema.json").read_text()
    )
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(projection)


def test_noncanonical_producer_ids_fail_closed() -> None:
    with pytest.raises(ValueError, match="AguaYLuz"):
        build_situation_projection(
            area_id="PR",
            valid_at="2026-07-21T17:00:00-04:00",
            aguayluz_records=[{"record_id": "copied-record"}],
            centinelas_events=[],
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("kind", "invented_kind"),
        ("content_sha256", "not-a-sha256"),
        ("evidence_tier", "T0"),
        ("quality", {"freshness": 42}),
    ],
)
def test_invalid_aguayluz_reference_fields_fail_closed(
    field: str, value: object
) -> None:
    record = {
        "record_id": "AYL_DROUGHT_CLASSIFICATION_OBSERVATION_0123456789abcdef0123",
        "kind": "classification_observation",
        "content_sha256": "a" * 64,
        "quality": {"freshness": "historical_snapshot"},
        "evidence_tier": "T1",
    }
    record[field] = value
    with pytest.raises(ValueError, match="producer contract"):
        build_situation_projection(
            area_id="PR",
            valid_at="2026-07-21T17:00:00-04:00",
            aguayluz_records=[record],
            centinelas_events=[],
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("event_id", "CEN_DROUGHT_not-canonical"),
        ("impact_type", "invented_impact"),
        ("content_sha256", "not-a-sha256"),
        ("evidence_tier", "T0"),
    ],
)
def test_invalid_centinelas_reference_fields_fail_closed(
    field: str, value: str
) -> None:
    event = {
        "event_id": "CEN_DROUGHT_0123456789abcdef0123",
        "impact_type": "wildfire_activity",
        "content_sha256": "b" * 64,
        "evidence_tier": "T2",
        "canonical_hydrology_embedded": False,
    }
    event[field] = value
    with pytest.raises(ValueError, match="producer contract"):
        build_situation_projection(
            area_id="PR",
            valid_at="2026-07-21T17:00:00-04:00",
            aguayluz_records=[],
            centinelas_events=[event],
        )


def test_duplicate_producer_ids_fail_closed() -> None:
    record = {
        "record_id": "AYL_DROUGHT_CLASSIFICATION_OBSERVATION_0123456789abcdef0123",
        "kind": "classification_observation",
        "content_sha256": "a" * 64,
        "quality": {},
        "evidence_tier": "T1",
    }
    with pytest.raises(ValueError, match="duplicate AguaYLuz record_id"):
        build_situation_projection(
            area_id="PR",
            valid_at="2026-07-21T17:00:00-04:00",
            aguayluz_records=[record, record],
            centinelas_events=[],
        )

    event = {
        "event_id": "CEN_DROUGHT_0123456789abcdef0123",
        "impact_type": "wildfire_activity",
        "content_sha256": "b" * 64,
        "evidence_tier": "T2",
        "canonical_hydrology_embedded": False,
    }
    with pytest.raises(ValueError, match="duplicate Centinelas event_id"):
        build_situation_projection(
            area_id="PR",
            valid_at="2026-07-21T17:00:00-04:00",
            aguayluz_records=[],
            centinelas_events=[event, event],
        )


@pytest.mark.parametrize("valid_at", ["2026-07-21", "not-a-date-time"])
def test_invalid_projection_timestamp_fails_closed(valid_at: str) -> None:
    with pytest.raises(ValueError, match="valid_at"):
        build_situation_projection(
            area_id="PR",
            valid_at=valid_at,
            aguayluz_records=[],
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
