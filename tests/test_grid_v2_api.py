"""Runtime contract tests for the PR grid V2 Cell_Profile API."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from hub.grid_v2 import grid_identity, load_pin
from server.backend import grid_v2_api as api

ROOT = Path(__file__).resolve().parents[1]
PIN_PATH = ROOT / "federation/spatial/pr_grid_geographic_v2.pin.json"
CELL = "PRG2:L1:R075:C0234"


def _profile(*, state: str, count):
    pin = load_pin(PIN_PATH, expected_consumer="thehub-pr")
    return {
        "Repository": "aguayluz-pr",
        "Domain": "hydrology",
        "Record_Count": count,
        "Category_Count": 0 if count in (None, 0) else 1,
        "Top_Record_IDs": [],
        "Earliest_Record": None,
        "Latest_Record": None,
        "Completeness": "UNKNOWN",
        "Freshness": "UNKNOWN",
        "Has_Data": bool(count),
        "Data_State": state,
        "Grid_Identity": grid_identity(pin, level="L1", cell_id=CELL),
    }


def test_router_exposes_canonical_grid_handoff_path():
    paths = {route.path for route in api.router.routes}
    assert "/grid/{grid_id}/{grid_version}/{level}/{cell_id}" in paths


def test_missing_profile_is_no_data_not_zero_records(monkeypatch):
    monkeypatch.setattr(api, "_profile_rows", lambda cell_id: [])
    result = api.cell_profile(
        "PR_GRID_GEOGRAPHIC_V2",
        "2.0.0-rc1",
        "L1",
        CELL,
    )
    assert result["Profile_Availability"] == "NO_DATA"
    assert result["Profile_Count"] == 0
    assert result["Profiles"] == []
    assert result["Grid_Identity"]["Cell_ID"] == CELL
    assert "NO_DATA is not ZERO_RECORDS" in result["note"]


def test_explicit_zero_records_is_preserved(monkeypatch):
    zero = _profile(state="ZERO_RECORDS", count=0)
    monkeypatch.setattr(api, "_profile_rows", lambda cell_id: [zero])
    result = api.cell_profile(
        "PR_GRID_GEOGRAPHIC_V2",
        "2.0.0-rc1",
        "L1",
        CELL,
    )
    assert result["Profile_Availability"] == "MATERIALIZED"
    assert result["Profiles"][0]["Data_State"] == "ZERO_RECORDS"
    assert result["Profiles"][0]["Record_Count"] == 0


def test_positive_materialized_profile_is_preserved(monkeypatch):
    positive = _profile(state="DATA_PRESENT", count=3)
    monkeypatch.setattr(api, "_profile_rows", lambda cell_id: [positive])
    result = api.cell_profile(
        "PR_GRID_GEOGRAPHIC_V2",
        "2.0.0-rc1",
        "L1",
        CELL,
    )
    assert result["Profiles"][0]["Data_State"] == "DATA_PRESENT"
    assert result["Profiles"][0]["Record_Count"] == 3
    assert result["Deep_Link"].endswith("/L1/" + CELL)


def test_stale_profile_identity_fails_closed(monkeypatch):
    stale = _profile(state="ZERO_RECORDS", count=0)
    stale["Grid_Identity"] = dict(stale["Grid_Identity"])
    stale["Grid_Identity"]["Grid_Manifest_SHA256"] = "0" * 64
    monkeypatch.setattr(api, "_profile_rows", lambda cell_id: [stale])
    with pytest.raises(HTTPException) as exc:
        api.cell_profile(
            "PR_GRID_GEOGRAPHIC_V2",
            "2.0.0-rc1",
            "L1",
            CELL,
        )
    assert exc.value.status_code == 500


@pytest.mark.parametrize(
    ("grid_id", "version", "level", "cell_id", "status"),
    [
        ("PR_GRID_LOGICAL_V1", "2.0.0-rc1", "L1", CELL, 409),
        ("PR_GRID_GEOGRAPHIC_V2", "2.0.0", "L1", CELL, 409),
        ("PR_GRID_GEOGRAPHIC_V2", "2.0.0-rc1", "L4", CELL, 422),
        (
            "PR_GRID_GEOGRAPHIC_V2",
            "2.0.0-rc1",
            "L1",
            "PRG2:L1:R999:C9999",
            422,
        ),
    ],
)
def test_wrong_identity_inputs_fail_closed(
    monkeypatch,
    grid_id,
    version,
    level,
    cell_id,
    status,
):
    monkeypatch.setattr(api, "_profile_rows", lambda selected: [])
    with pytest.raises(HTTPException) as exc:
        api.cell_profile(grid_id, version, level, cell_id)
    assert exc.value.status_code == status


def test_invalid_zero_records_contract_fails_closed(monkeypatch):
    broken = _profile(state="ZERO_RECORDS", count=1)
    monkeypatch.setattr(api, "_profile_rows", lambda cell_id: [broken])
    with pytest.raises(HTTPException, match="ZERO_RECORDS"):
        api.cell_profile(
            "PR_GRID_GEOGRAPHIC_V2",
            "2.0.0-rc1",
            "L1",
            CELL,
        )
