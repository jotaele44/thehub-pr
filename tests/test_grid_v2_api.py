"""Read-only grid V2 handoff and profile provenance smoke gates."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from hub.grid_v2 import grid_identity, load_pin
from server.backend.grid_v2_api import PIN_PATH, PROFILE_VERSION, cell_handoff, router

ROOT = Path(__file__).resolve().parents[1]


def _valid_profile(identity):
    return {
        "Schema_Version": PROFILE_VERSION,
        "Grid_Identity": identity,
        "Repository": "aguayluz-pr",
        "Profile_Type": "water_hydrology",
        "Cell_ID": "PRG2:L1:R075:C0234",
        "Data_State": "ZERO_RECORDS",
        "Coverage_State": "VERIFIED",
        "Record_Count": 0,
        "Category_Count": 0,
        "Categories": {},
        "Top_Record_IDs": [],
        "Shared_Boundary_Record_Count": 0,
        "Identity_Default": "CANDIDATE_NOT_IDENTITY",
        "Geometry_Included": False,
    }


def _write_profile_fixture(tmp_path, row):
    pin = load_pin(PIN_PATH, expected_consumer="thehub-pr")
    directory = tmp_path / "aguayluz-pr"
    directory.mkdir(exist_ok=True)
    artifact = directory / "L1.jsonl"
    artifact.write_text(json.dumps(row) + "\n")
    receipt = {
        "Output_SHA256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "Repository": "aguayluz-pr",
        "Grid_Identity": grid_identity(pin, level="L1"),
        "Geometry_Copied": False,
        "State": "CANDIDATE_NOT_CANONICAL",
    }
    (directory / "L1.receipt.json").write_text(json.dumps(receipt) + "\n")


def test_profile_schema_matches_runtime_version_and_full_grid_identity():
    schema = json.loads((ROOT / "schemas/cell_profile_v2.schema.json").read_text())
    assert schema["properties"]["Schema_Version"]["const"] == PROFILE_VERSION
    required = set(schema["properties"]["Grid_Identity"]["required"])
    assert {
        "Grid_Manifest_SHA256",
        "Cell_Schema_SHA256",
        "Binding_Schema_SHA256",
        "Mask_Schema_SHA256",
    } <= required
    assert schema["properties"]["Grid_Identity"]["additionalProperties"] is False


def test_handoff_routes_and_uncovered_cell(monkeypatch):
    routes = {r.path for r in router.routes}
    path = "/grid/{grid_id}/{grid_version}/{level}/{cell_id}"
    assert path in routes
    assert "/api" + path in routes
    monkeypatch.delenv("PRII_GRID_V2_PROFILE_ROOT", raising=False)
    result = cell_handoff(
        "PR_GRID_GEOGRAPHIC_V2",
        "2.0.0-rc1",
        "L1",
        "PRG2:L1:R075:C0234",
    )
    assert result["Cell_Profile_State"] == "NO_DATA"
    assert result["Profiles"] == []
    assert result["Grid_Identity"]["Cell_ID"] == "PRG2:L1:R075:C0234"
    assert result["Geometry_Included"] is False


def test_wrong_version_rejected():
    with pytest.raises(HTTPException) as exc:
        cell_handoff(
            "PR_GRID_GEOGRAPHIC_V2",
            "1.0.0",
            "L1",
            "PRG2:L1:R075:C0234",
        )
    assert exc.value.status_code == 422


def test_domain_profile_is_read_only_and_identity_bound(monkeypatch, tmp_path):
    pin = load_pin(PIN_PATH, expected_consumer="thehub-pr")
    identity = grid_identity(
        pin,
        level="L1",
        cell_id="PRG2:L1:R075:C0234",
    )
    row = _valid_profile(identity)
    _write_profile_fixture(tmp_path, row)
    monkeypatch.setenv("PRII_GRID_V2_PROFILE_ROOT", str(tmp_path))

    result = cell_handoff(
        "PR_GRID_GEOGRAPHIC_V2",
        "2.0.0-rc1",
        "L1",
        "PRG2:L1:R075:C0234",
    )
    assert result["Cell_Profile_State"] == "AVAILABLE"
    assert result["Profiles"][0]["Schema_Version"] == PROFILE_VERSION
    assert result["Profiles"][0]["Data_State"] == "ZERO_RECORDS"

    row["Grid_Identity"] = {"Grid_ID": "WRONG"}
    _write_profile_fixture(tmp_path, row)
    with pytest.raises(HTTPException) as exc:
        cell_handoff(
            "PR_GRID_GEOGRAPHIC_V2",
            "2.0.0-rc1",
            "L1",
            "PRG2:L1:R075:C0234",
        )
    assert exc.value.status_code == 503


def test_stale_profile_schema_version_fails_closed(monkeypatch, tmp_path):
    pin = load_pin(PIN_PATH, expected_consumer="thehub-pr")
    identity = grid_identity(
        pin,
        level="L1",
        cell_id="PRG2:L1:R075:C0234",
    )
    row = _valid_profile(identity)
    row["Schema_Version"] = "pr-grid-v2-cell-profile/1.0"
    _write_profile_fixture(tmp_path, row)
    monkeypatch.setenv("PRII_GRID_V2_PROFILE_ROOT", str(tmp_path))

    with pytest.raises(HTTPException) as exc:
        cell_handoff(
            "PR_GRID_GEOGRAPHIC_V2",
            "2.0.0-rc1",
            "L1",
            "PRG2:L1:R075:C0234",
        )
    assert exc.value.status_code == 503


def test_no_data_cannot_claim_verified_coverage(monkeypatch, tmp_path):
    pin = load_pin(PIN_PATH, expected_consumer="thehub-pr")
    identity = grid_identity(
        pin,
        level="L1",
        cell_id="PRG2:L1:R075:C0234",
    )
    row = _valid_profile(identity)
    row["Data_State"] = "NO_DATA"
    row["Coverage_State"] = "VERIFIED"
    _write_profile_fixture(tmp_path, row)
    monkeypatch.setenv("PRII_GRID_V2_PROFILE_ROOT", str(tmp_path))

    with pytest.raises(HTTPException) as exc:
        cell_handoff(
            "PR_GRID_GEOGRAPHIC_V2",
            "2.0.0-rc1",
            "L1",
            "PRG2:L1:R075:C0234",
        )
    assert exc.value.status_code == 503
