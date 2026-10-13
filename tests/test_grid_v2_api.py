"""Read-only grid V2 handoff and profile provenance smoke gates."""
from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

from hub.grid_v2 import grid_identity, load_pin
from server.backend.grid_v2_api import PIN_PATH, cell_handoff, router


def test_handoff_routes_and_uncovered_cell(monkeypatch):
    routes = {r.path for r in router.routes}
    path = "/grid/{grid_id}/{grid_version}/{level}/{cell_id}"
    assert path in routes
    assert "/api" + path in routes
    monkeypatch.delenv("PRII_GRID_V2_PROFILE_ROOT", raising=False)
    result = cell_handoff("PR_GRID_GEOGRAPHIC_V2", "2.0.0-rc1", "L1", "PRG2:L1:R075:C0234")
    assert result["Cell_Profile_State"] == "NO_DATA"
    assert result["Profiles"] == []
    assert result["Grid_Identity"]["Cell_ID"] == "PRG2:L1:R075:C0234"
    assert result["Geometry_Included"] is False


def test_wrong_version_rejected():
    with pytest.raises(HTTPException) as exc:
        cell_handoff("PR_GRID_GEOGRAPHIC_V2", "1.0.0", "L1", "PRG2:L1:R075:C0234")
    assert exc.value.status_code == 422


def test_domain_profile_is_read_only(monkeypatch, tmp_path):
    pin = load_pin(PIN_PATH, expected_consumer="thehub-pr")
    identity = grid_identity(pin, level="L1", cell_id="PRG2:L1:R075:C0234")
    directory = tmp_path / "aguayluz-pr"
    directory.mkdir()
    row = {
        "Grid_Identity": identity, "Cell_ID": "PRG2:L1:R075:C0234",
        "Repository": "aguayluz-pr", "Data_State": "ZERO_RECORDS",
        "Geometry_Included": False, "Record_Count": 0,
    }
    artifact = directory / "L1.jsonl"
    artifact.write_text(json.dumps(row) + "\n")
    monkeypatch.setenv("PRII_GRID_V2_PROFILE_ROOT", str(tmp_path))
    result = cell_handoff("PR_GRID_GEOGRAPHIC_V2", "2.0.0-rc1", "L1", "PRG2:L1:R075:C0234")
    assert result["Cell_Profile_State"] == "AVAILABLE"
    assert result["Profiles"][0]["Data_State"] == "ZERO_RECORDS"
    row["Grid_Identity"] = {"Grid_ID": "WRONG"}
    artifact.write_text(json.dumps(row) + "\n")
    with pytest.raises(HTTPException) as exc:
        cell_handoff("PR_GRID_GEOGRAPHIC_V2", "2.0.0-rc1", "L1", "PRG2:L1:R075:C0234")
    assert exc.value.status_code == 503
