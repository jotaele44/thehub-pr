import json

import pytest

from prii_export_utils import (
    STATE_SCHEMA_VERSION,
    SourceRunState,
    fid,
    monitor_id,
    record_run,
    resolve_last_success,
    source_monitor_row,
)

LINEAGE = {"producer_script": "scripts/federation_export.py", "producer_phase": "SOURCE_MONITOR",
           "source_inputs": ["config/hydromet_sources.v1.json"]}


def _row(**overrides):
    base = dict(
        producer="aguayluz-pr", source_ref="nwps_gauges", name="NWPS river gauges",
        declared_status="unknown", cadence="realtime",
        last_success_at="2026-11-08T15:47:31Z", last_success_basis="OUTPUT_DERIVED",
        lineage=LINEAGE, created_at="2026-11-11T00:00:00Z", extracted_at="2026-11-11T00:00:00Z",
    )
    base.update(overrides)
    return source_monitor_row(**base)


def test_monitor_id_is_deterministic_and_namespaced():
    assert monitor_id("aguayluz-pr", "nwps_gauges") == fid("mon", "aguayluz-pr", "nwps_gauges")
    assert monitor_id("aguayluz-pr", "nwps_gauges").startswith("mon_")
    assert monitor_id("aguayluz-pr", "a") != monitor_id("ovnis-pr", "a")


def test_row_carries_every_required_field():
    row = _row(cadence_window_seconds=7200, evidence_tier="T1", registry_path="config/hydromet_sources.v1.json")
    for key in ("monitor_id", "source_ref", "name", "declared_status", "cadence", "last_success_basis",
                "lineage", "synthetic", "created_at", "extracted_at"):
        assert key in row
    assert row["synthetic"] is False and row["cadence_window_seconds"] == 7200


@pytest.mark.parametrize("overrides,match", [
    ({"declared_status": "healthy"}, "declared_status"),
    ({"cadence": "fortnightly"}, "cadence"),
    ({"last_success_basis": "GUESSED"}, "last_success_basis"),
    ({"last_success_basis": "NOT_RECORDED"}, "null exactly when"),
    ({"last_success_at": None}, "null exactly when"),
    ({"evidence_tier": "T5"}, "evidence_tier"),
    ({"last_attempt_status": "ok"}, "last_attempt_status"),
    ({"cadence_window_seconds": 0}, "positive"),
    ({"source_ref": ""}, "required"),
])
def test_row_rejects_invalid_input(overrides, match):
    with pytest.raises(ValueError, match=match):
        _row(**overrides)


def test_not_recorded_row_has_null_time():
    row = _row(last_success_at=None, last_success_basis="NOT_RECORDED")
    assert row["last_success_at"] is None


@pytest.mark.parametrize("receipt,derived,expected", [
    (None, None, (None, "NOT_RECORDED")),
    ("2026-11-08T10:00:00Z", None, ("2026-11-08T10:00:00Z", "RUN_RECEIPT")),
    (None, "2026-11-08T10:00:00Z", ("2026-11-08T10:00:00Z", "OUTPUT_DERIVED")),
    ("2026-11-08T10:00:00Z", "2026-11-08T09:00:00Z", ("2026-11-08T10:00:00Z", "RUN_RECEIPT")),
    ("2026-11-08T10:00:00Z", "2026-11-08T11:00:00.5Z", ("2026-11-08T11:00:00.5Z", "OUTPUT_DERIVED")),
    ("2026-11-08T10:00:00Z", "2026-11-08T10:00:00+00:00", ("2026-11-08T10:00:00Z", "RUN_RECEIPT")),
])
def test_resolve_last_success_prefers_the_latest_and_ties_to_receipt(receipt, derived, expected):
    state_row = {"last_success_at": receipt} if receipt else None
    assert resolve_last_success(state_row, derived) == expected


def test_state_records_attempts_and_successes(tmp_path):
    path = tmp_path / "data" / "source_run_state.json"
    record_run(path, "nwps_gauges", "success", "2026-11-08T10:00:00Z")
    record_run(path, "nwps_gauges", "failure", "2026-11-09T10:00:00Z")
    record_run(path, "stage_iv_pr", "failure", "2026-11-09T11:00:00Z")
    state = SourceRunState.load(path)
    assert state.get("nwps_gauges") == {
        "last_attempt_at": "2026-11-09T10:00:00Z", "last_attempt_status": "failure",
        "last_success_at": "2026-11-08T10:00:00Z",
    }
    # A source that never succeeded keeps an explicit null success.
    assert state.get("stage_iv_pr")["last_success_at"] is None
    data = json.loads(path.read_text())
    assert data["schema_version"] == STATE_SCHEMA_VERSION
    assert list(data["sources"]) == sorted(data["sources"])
    assert path.read_text().endswith("\n")
    assert not list(path.parent.glob(".source_run_state.*.tmp"))


def test_state_load_handles_missing_and_rejects_foreign_files(tmp_path):
    assert SourceRunState.load(tmp_path / "missing.json").sources == {}
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema_version": "other", "sources": {}}))
    with pytest.raises(ValueError, match="schema_version"):
        SourceRunState.load(bad)


def test_state_rejects_bad_status_and_time(tmp_path):
    state = SourceRunState(tmp_path / "s.json")
    with pytest.raises(ValueError, match="status"):
        state.record("x", "ok")
    with pytest.raises(ValueError):
        state.record("x", "success", "not a time")


def test_rows_validate_against_the_hubs_frozen_schema():
    # The schema lives in this repository (thehub-pr/schemas); the package's CI job
    # installs the repo's dev extras, so jsonschema is available there.
    jsonschema = pytest.importorskip("jsonschema")
    from pathlib import Path

    schema_path = Path(__file__).resolve().parents[3] / "schemas" / "federation_source_monitor.schema.json"
    if not schema_path.exists():
        pytest.skip("not inside a thehub-pr checkout")
    validator = jsonschema.Draft7Validator(json.loads(schema_path.read_text()))
    for row in (_row(), _row(last_success_at=None, last_success_basis="NOT_RECORDED"),
                _row(last_success_basis="RUN_RECEIPT", last_attempt_at="2026-11-09T00:00:00Z",
                     last_attempt_status="failure", cadence_window_seconds=7200, evidence_tier="T1")):
        assert list(validator.iter_errors(row)) == []
