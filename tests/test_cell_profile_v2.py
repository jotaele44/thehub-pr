"""Certification tests for additive PR grid V2 Cell_Profile contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
import pytest
from fastapi import HTTPException

from hub.cell_profile_v2 import (
    CellProfileV2Error,
    build_cell_profile_v2,
    build_unmigrated_hub_profile,
)
from hub.grid_v2 import load_pin
from server.backend.grid_v2_api import cell_profile_v2

ROOT = Path(__file__).resolve().parents[1]
PIN = ROOT / "federation/spatial/pr_grid_geographic_v2.pin.json"
V1_SCHEMA = ROOT / "schemas/cell_profile.schema.json"
V2_SCHEMA = ROOT / "schemas/cell_profile_v2.schema.json"
V1_FROZEN_SHA256 = "c79391e107f7aa95cbf4c4d0b76487f7e0ae51f8dc7e47286045e435105bfc52"


def _pin():
    return load_pin(PIN, expected_consumer="thehub-pr")


def _schema():
    return json.loads(V2_SCHEMA.read_text(encoding="utf-8"))


def test_v1_cell_profile_contract_is_byte_unchanged():
    assert hashlib.sha256(V1_SCHEMA.read_bytes()).hexdigest() == V1_FROZEN_SHA256


def test_unmigrated_profile_is_truthful_and_schema_valid():
    profile = build_unmigrated_hub_profile(
        _pin(),
        level="L1",
        cell_id="PRG2:L1:R075:C0234",
    )
    assert profile["Data_State"] == "UNKNOWN"
    assert profile["Record_Count"] is None
    assert profile["Migration_State"] == "UNMIGRATED"
    assert profile["Summary"]["zero_records_claimed"] is False
    assert profile["Geometry_Included"] is False
    assert profile["Grid_Identity"]["Cell_ID"] == "PRG2:L1:R075:C0234"
    assert profile["Deep_Link"] == (
        "/grid/PR_GRID_GEOGRAPHIC_V2/2.0.0-rc1/"
        "L1/PRG2:L1:R075:C0234"
    )
    jsonschema.validate(profile, _schema())


def test_zero_records_and_no_data_are_not_interchangeable():
    zero = build_cell_profile_v2(
        _pin(),
        repository="thehub-pr",
        profile_type="federation_summary",
        level="L1",
        cell_id="PRG2:L1:R000:C0000",
        data_state="ZERO_RECORDS",
        record_count=0,
        migration_state="VERIFIED_CROSSWALK",
    )
    no_data = build_cell_profile_v2(
        _pin(),
        repository="thehub-pr",
        profile_type="federation_summary",
        level="L1",
        cell_id="PRG2:L1:R000:C0000",
        data_state="NO_DATA",
        record_count=None,
        migration_state="VERIFIED_CROSSWALK",
    )
    assert zero["Data_State"] == "ZERO_RECORDS"
    assert zero["Record_Count"] == 0
    assert no_data["Data_State"] == "NO_DATA"
    assert no_data["Record_Count"] is None
    jsonschema.validate(zero, _schema())
    jsonschema.validate(no_data, _schema())


@pytest.mark.parametrize(
    ("data_state", "record_count"),
    [
        ("ZERO_RECORDS", 1),
        ("HAS_DATA", 0),
        ("NO_DATA", 0),
        ("UNKNOWN", 0),
    ],
)
def test_count_state_mismatches_fail_closed(data_state, record_count):
    with pytest.raises(CellProfileV2Error):
        build_cell_profile_v2(
            _pin(),
            repository="thehub-pr",
            profile_type="federation_summary",
            level="L1",
            cell_id="PRG2:L1:R000:C0000",
            data_state=data_state,
            record_count=record_count,
            migration_state="VERIFIED_CROSSWALK",
        )


def test_unmigrated_profile_cannot_claim_observed_records():
    with pytest.raises(CellProfileV2Error, match="UNMIGRATED"):
        build_cell_profile_v2(
            _pin(),
            repository="thehub-pr",
            profile_type="federation_summary",
            level="L1",
            cell_id="PRG2:L1:R000:C0000",
            data_state="HAS_DATA",
            record_count=7,
            migration_state="UNMIGRATED",
        )


@pytest.mark.parametrize("field", ["geometry", "coordinates", "bbox", "polygon"])
def test_summary_cannot_smuggle_geometry(field):
    with pytest.raises(CellProfileV2Error, match="must not carry canonical geometry"):
        build_cell_profile_v2(
            _pin(),
            repository="thehub-pr",
            profile_type="federation_summary",
            level="L1",
            cell_id="PRG2:L1:R000:C0000",
            data_state="UNKNOWN",
            record_count=None,
            migration_state="UNMIGRATED",
            summary={field: {}},
        )


def test_wrong_cell_level_fails_closed():
    with pytest.raises(CellProfileV2Error, match="does not match requested level"):
        build_unmigrated_hub_profile(
            _pin(),
            level="L1",
            cell_id="PRG2:L2:R000:C0000",
        )


def test_api_returns_truthful_unmigrated_profile():
    profile = cell_profile_v2(
        grid_id="PR_GRID_GEOGRAPHIC_V2",
        grid_version="2.0.0-rc1",
        level="L1",
        cell_id="PRG2:L1:R075:C0234",
        as_of=None,
    )
    assert profile["Repository"] == "thehub-pr"
    assert profile["Data_State"] == "UNKNOWN"
    assert profile["Record_Count"] is None
    assert profile["Migration_State"] == "UNMIGRATED"
    jsonschema.validate(profile, _schema())


@pytest.mark.parametrize(
    ("grid_id", "grid_version"),
    [
        ("PR_GRID_LOGICAL_V1", "2.0.0-rc1"),
        ("PR_GRID_GEOGRAPHIC_V2", "2.0.0"),
    ],
)
def test_api_wrong_grid_identity_fails_closed(grid_id, grid_version):
    with pytest.raises(HTTPException) as exc:
        cell_profile_v2(
            grid_id=grid_id,
            grid_version=grid_version,
            level="L1",
            cell_id="PRG2:L1:R075:C0234",
            as_of=None,
        )
    assert exc.value.status_code == 422


def test_v2_cell_profile_route_is_mounted_on_canonical_app():
    from server.backend import main as backend_main

    paths = {getattr(route, "path", None) for route in backend_main.app.routes}
    assert (
        "/api/grid/{grid_id}/{grid_version}/{level}/{cell_id}/profile"
        in paths
    )
