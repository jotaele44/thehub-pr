"""FEDERATION_EPISTEMIC_STATE_CONTRACT_V1: positive and negative fixtures.

Each axis is tested for the value it must produce and for the promotion it
must refuse (directive §43, §64 invariants).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hub import epistemic as ep

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((REPO_ROOT / "schemas/federation/epistemic_state.v1.schema.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "axis, values",
    [
        ("data_stage", ep.DATA_STAGES),
        ("epistemic_class", ep.EPISTEMIC_CLASSES),
        ("epistemic_class_basis", ep.EPISTEMIC_CLASS_BASES),
        ("identity_state", ep.IDENTITY_STATES),
        ("identity_scope", ep.IDENTITY_SCOPES),
        ("source_state", ep.SOURCE_STATES),
        ("temporal_state", ep.TEMPORAL_STATES),
        ("temporal_precision", ep.TEMPORAL_PRECISIONS),
        ("observation_state", ep.OBSERVATION_STATES),
        ("geometry_precision", ep.GEOMETRY_PRECISIONS),
        ("edge_state", ep.EDGE_STATES),
        ("contradiction_state", ep.CONTRADICTION_STATES),
    ],
)
def test_python_and_schema_enumerations_match(axis, values):
    assert tuple(SCHEMA["$defs"][axis]["enum"]) == values


def test_schema_is_candidate_not_frozen():
    assert SCHEMA["x-status"] == "CANDIDATE" == ep.CONTRACT_STATUS
    frozen = (REPO_ROOT / "schemas/FROZEN.sha256").read_text(encoding="utf-8")
    assert "epistemic_state" not in frozen


def test_pick_fails_closed_and_reports():
    errors: list = []
    assert ep.pick("MEASURED", ep.EPISTEMIC_CLASSES, "UNCLASSIFIED", errors, "x") == "MEASURED"
    assert ep.pick("measured", ep.EPISTEMIC_CLASSES, "UNCLASSIFIED", errors, "x") == "UNCLASSIFIED"
    assert ep.pick(None, ep.EPISTEMIC_CLASSES, "UNCLASSIFIED", errors, "x") == "UNCLASSIFIED"
    assert errors == ["x: 'measured' is not a valid value"]


# ── epistemic class ───────────────────────────────────────────────────────────


def test_declared_class_is_used():
    row = {"evidence_state": {"epistemic_class": "MEASURED"}}
    assert ep.epistemic_class_for(row) == ("MEASURED", "PRODUCER_DECLARED")


def test_undeclared_class_is_unclassified_not_guessed():
    assert ep.epistemic_class_for({"attributes": {"value": 3.2}}) == ("UNCLASSIFIED", "NONE")
    assert ep.epistemic_class_for({"evidence_state": "MEASURED"}) == ("UNCLASSIFIED", "NONE")


def test_hub_computed_rows_are_computed():
    assert ep.epistemic_class_for({}, hub_computed=True) == ("COMPUTED", "PRODUCER_DECLARED")


def test_interpretive_without_basis_is_rejected():
    errors: list = []
    row = {"evidence_state": {"epistemic_class": "INTERPRETIVE"}}
    assert ep.epistemic_class_for(row, errors=errors) == ("UNCLASSIFIED", "NONE")
    assert "INTERPRETIVE requires interpretation_basis" in errors[0]
    ok = {"evidence_state": {"epistemic_class": "INTERPRETIVE", "interpretation_basis": "void model from GPR"}}
    assert ep.epistemic_class_for(ok) == ("INTERPRETIVE", "PRODUCER_DECLARED")


def test_data_stage():
    assert ep.data_stage_for({}) == "CANONICAL"
    assert ep.data_stage_for({}, hub_computed=True) == "COMPUTATION"
    assert ep.data_stage_for({"evidence_state": {"data_stage": "FINDING"}}) == "FINDING"


# ── geometry ──────────────────────────────────────────────────────────────────


def test_documented_point_is_observed_point():
    row = {"location": {"lat": 18.4, "lon": -66.1}, "attributes": {"coordinate_method": "SURVEYED"}}
    geo = ep.geometry_for(row)
    assert geo["geometry_precision"] == "OBSERVED_POINT"
    assert geo["geometry"] == {"type": "Point", "coordinates": [-66.1, 18.4]}


@pytest.mark.parametrize("method", ["DERIVED_CENTROID", "GEOCODED_LOCALITY", "FIRST_VERTEX", "DERIVED_AVERAGE"])
def test_representative_point_never_becomes_observed(method):
    row = {"location": {"lat": 18.4, "lon": -66.1}, "attributes": {"coordinate_method": method}}
    assert ep.geometry_for(row)["geometry_precision"] == "REPRESENTATIVE_POINT"


def test_declared_observed_point_contradicting_method_is_refused():
    errors: list = []
    row = {
        "location": {"lat": 18.4, "lon": -66.1},
        "evidence_state": {"geometry_precision": "OBSERVED_POINT", "coordinate_method": "DERIVED_CENTROID"},
    }
    geo = ep.geometry_for(row, errors)
    assert geo["geometry_precision"] == "REPRESENTATIVE_POINT"
    assert "contradicts coordinate_method DERIVED_CENTROID" in errors[0]


def test_declared_point_without_coordinates_is_refused():
    errors: list = []
    row = {"location": {"municipality": "Guayama"}, "evidence_state": {"geometry_precision": "OBSERVED_POINT"}}
    assert ep.geometry_for(row, errors)["geometry_precision"] == "AREA_REFERENCE"
    assert "declared without coordinates" in errors[0]


def test_declared_precision_is_used():
    row = {"latitude": 18.0, "longitude": -66.0, "evidence_state": {"geometry_precision": "INTERPRETED_POINT"}}
    geo = ep.geometry_for(row)
    assert geo["geometry_precision"] == "INTERPRETED_POINT"
    assert geo["geometry_basis"] == "producer declared INTERPRETED_POINT"


def test_repeated_coordinates_are_not_promoted():
    rows = [{"location": {"lat": 17.984, "lon": -66.113}} for _ in range(25)]
    assert {ep.geometry_for(r)["geometry_precision"] for r in rows} == {"UNKNOWN"}


def test_municipality_only_is_area_reference():
    geo = ep.geometry_for({"location": {"municipality": "Guayama"}})
    assert geo["geometry_precision"] == "AREA_REFERENCE"
    assert geo["geometry"] is None
    assert geo["area_reference"] == "Guayama"


def test_no_geometry_and_bad_coordinates():
    assert ep.geometry_for({})["geometry_precision"] == "UNKNOWN"
    assert ep.geometry_for({"location": {"lat": "north", "lon": -66}})["geometry"] is None


# ── time ──────────────────────────────────────────────────────────────────────


def test_bounded_and_dated_precisions():
    assert ep.temporal_for({"date_precision": "uncertain_range", "observed_at": "1974-03-01T00:00:00Z"})[
        "temporal_precision"] == "BOUNDED_INTERVAL"
    day = ep.temporal_for({"date_local": "1974-03-12", "observed_at": "1974-03-12T00:00:00-04:00"})
    assert (day["temporal_precision"], day["observed_at"]) == ("DATE_ONLY", "1974-03-12")


def test_year_only_event_does_not_acquire_invented_time():
    row = {"date_local": "1929", "date_precision": "year", "observed_at": "1929-01-01T00:00:00-04:00"}
    t = ep.temporal_for(row)
    assert t["temporal_precision"] == "YEAR_ONLY"
    assert t["observed_at"] == "1929"
    assert "1929-01-01T00:00:00-04:00" in t["temporal_basis"]


@pytest.mark.parametrize("date_local, expected", [("1974", "YEAR_ONLY"), ("1974-03", "MONTH_YEAR")])
def test_date_local_patterns(date_local, expected):
    t = ep.temporal_for({"date_local": date_local})
    assert t["temporal_precision"] == expected
    assert t["observed_at"] == date_local


def test_undeclared_timestamp_precision_is_unknown():
    t = ep.temporal_for({"observed_at": "2026-09-01T10:00:00Z"})
    assert t["temporal_precision"] == "UNKNOWN"
    assert t["observed_at"] == "2026-09-01T10:00:00Z"
    assert ep.temporal_for({})["observed_at"] is None


def test_declared_exact_timestamp():
    row = {"observed_at": "2026-09-01T10:00:00Z", "evidence_state": {"temporal_precision": "EXACT_TIMESTAMP"}}
    assert ep.temporal_for(row)["temporal_precision"] == "EXACT_TIMESTAMP"


def test_parse_instant():
    assert ep.parse_instant("2026-09-01") is None
    assert ep.parse_instant("not-a-timeTx") is None
    assert ep.parse_instant("2026-09-01T10:00:00").tzinfo is not None
    assert ep.parse_instant(None) is None


def test_temporal_states():
    live = {"observed_at": "2026-09-25T11:59:30Z", "evidence_state": {"expected_cadence_seconds": 60, "live_feed": True}}
    assert ep.temporal_state_at(live, NOW)[0] == "LIVE"
    current = {"observed_at": "2026-09-25T11:30:00Z", "evidence_state": {"expected_cadence_seconds": 3600}}
    assert ep.temporal_state_at(current, NOW)[0] == "CURRENT"
    stale = {"observed_at": "2026-09-25T10:00:00Z", "evidence_state": {"expected_cadence_seconds": 60, "live_feed": True}}
    assert ep.temporal_state_at(stale, NOW)[0] == "STALE"
    assert ep.temporal_state_at({"end_at": "2026-01-01T00:00:00Z"}, NOW)[0] == "HISTORICAL"
    window = {"start_at": "2026-09-01T00:00:00Z", "end_at": "2026-12-01T00:00:00Z"}
    assert ep.temporal_state_at(window, NOW)[0] == "CURRENT"
    assert ep.temporal_state_at({"date_local": "1929"}, NOW)[0] == "HISTORICAL"
    assert ep.temporal_state_at({}, NOW)[0] == "UNKNOWN"
    no_time = {"evidence_state": {"expected_cadence_seconds": 60}}
    assert ep.temporal_state_at(no_time, NOW)[0] == "UNKNOWN"


def test_live_is_never_claimed_without_declared_cadence():
    fresh = {"observed_at": "2026-09-25T11:59:59Z", "extracted_at": "2026-09-25T11:59:59Z"}
    assert ep.temporal_state_at(fresh, NOW)[0] == "HISTORICAL"


# ── source ────────────────────────────────────────────────────────────────────

SOURCES = {
    "src_ok": {"source_id": "src_ok", "source_url": "https://example.gov/record"},
    "src_none": {"source_id": "src_none", "source_ref": "none", "source_type": "none"},
    "src_blocked": {"source_id": "src_blocked", "source_url": "https://x", "status": "blocked"},
}


def test_source_lineage_resolves():
    assert ep.source_state_for({"source_id": "src_ok"}, SOURCES)[0] == "SOURCE_BOUND"


def test_missing_source_does_not_fabricate_binding():
    assert ep.source_state_for({}, SOURCES) == ("SOURCE_MISSING", "no source reference")
    assert ep.source_state_for({"source_url": "https://news"}, SOURCES)[0] == "SOURCE_REPORTED"


def test_unresolvable_reference_is_reported_not_missing():
    assert ep.source_state_for({"source_id": "src_elsewhere"}, SOURCES)[0] == "SOURCE_REPORTED"


def test_source_without_locator_and_blocked_source():
    assert ep.source_state_for({"source_id": "src_none"}, SOURCES)[0] == "SOURCE_REPORTED"
    assert ep.source_state_for({"source_id": "src_blocked"}, SOURCES)[0] == "SOURCE_BLOCKED"


# ── observation ───────────────────────────────────────────────────────────────


def test_not_observed_never_becomes_observed_absent():
    errors: list = []
    row = {"evidence_state": {"observation_state": "OBSERVED_ABSENT"}}
    assert ep.observation_state_for(row, errors)[0] == "NOT_OBSERVED"
    assert "requires observation_absence_basis" in errors[0]
    assert ep.observation_state_for({"attributes": {"value": None}})[0] == "UNKNOWN"


def test_declared_absence_with_coverage_basis():
    row = {"evidence_state": {"observation_state": "OBSERVED_ABSENT", "observation_absence_basis": "full ADS-B coverage 60 nm"}}
    state, basis = ep.observation_state_for(row)
    assert state == "OBSERVED_ABSENT"
    assert "full ADS-B coverage" in basis
    assert ep.observation_state_for({"evidence_state": {"observation_state": "OBSERVED_PRESENT"}})[0] == "OBSERVED_PRESENT"


# ── identity ──────────────────────────────────────────────────────────────────


def test_known_manifestations_bind():
    identity = ep.identity_for({}, {"state": "RESOLVED", "match_class": "EXACT_IDENTIFIER"})
    assert identity == {"identity_state": "BOUND", "identity_scope": "FEDERATION",
                        "identity_basis": "registry RESOLVED via EXACT_IDENTIFIER"}


def test_similar_labels_do_not_silently_merge():
    assert ep.identity_for({}, {"state": "CANDIDATE", "match_class": None})["identity_state"] == "CANDIDATE"
    assert ep.identity_for({}, {"state": "RESOLVED", "match_class": "PROVEN_RELATIONSHIP"})["identity_state"] == "UNRESOLVED"
    assert ep.identity_for({}, {"state": "REJECTED"})["identity_state"] == "UNRESOLVED"
    assert ep.identity_for({}, {"conflicting": True})["identity_state"] == "CONFLICTING"


def test_identity_fails_closed_without_adjudication():
    assert ep.identity_for({}) == {"identity_state": "UNRESOLVED", "identity_scope": "PRODUCER_LOCAL",
                                   "identity_basis": "no identity adjudication"}
    declared = ep.identity_for({"evidence_state": {"identity_state": "CANDIDATE"}})
    assert (declared["identity_state"], declared["identity_basis"]) == ("CANDIDATE", "producer declared")


# ── edges ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("basis", ["normalized_name", "location", "award_transaction_date"])
def test_weak_hub_correlations_stay_candidate(basis):
    state, _ = ep.edge_state_for({"match_basis": basis}, hub_computed=True, source_state="SOURCE_BOUND")
    assert state == "CANDIDATE"


def test_shared_identifier_is_computed_not_documented():
    assert ep.edge_state_for({"match_basis": "external_id:uei"}, hub_computed=True, source_state="SOURCE_BOUND")[0] == "COMPUTED"
    assert ep.edge_state_for({"match_basis": "mystery"}, hub_computed=True, source_state="SOURCE_BOUND")[0] == "UNKNOWN"


def test_documented_contract_edge_requires_bound_source():
    assert ep.edge_state_for({"relationship_type": "FUNDED_BY"}, hub_computed=False, source_state="SOURCE_BOUND")[0] == "DOCUMENTED"
    assert ep.edge_state_for({"relationship_type": "FUNDED_BY"}, hub_computed=False, source_state="SOURCE_MISSING")[0] == "UNKNOWN"


def test_producer_proximity_edge_is_not_documented():
    row = {"relationship_type": "near", "match_basis": "spatial_proximity"}
    assert ep.edge_state_for(row, hub_computed=False, source_state="SOURCE_BOUND")[0] == "CANDIDATE"
