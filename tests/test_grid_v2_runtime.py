"""Certification tests for the shared PR grid V2 runtime pin reader."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from hub.grid_v2 import (
    AUTHORITY_COMMIT,
    BINDING_SCHEMA_SHA256,
    CELL_SCHEMA_SHA256,
    CRS,
    EXPECTED_DEFAULT_LEVELS,
    GRID_ID,
    GRID_MANIFEST_SHA256,
    GRID_VERSION,
    MASK_SCHEMA_SHA256,
    GridV2PinError,
    attach_grid_identity,
    build_grid_deep_link,
    grid_identity,
    load_pin,
    validate_cell_id,
    validate_pin_set,
)

ROOT = Path(__file__).resolve().parents[1]
PIN_PATH = ROOT / "federation/spatial/pr_grid_geographic_v2.pin.json"
TEMPLATE_PATH = ROOT / "federation-templates/spatial/pr_grid_v2_runtime.py"
RUNTIME_PATH = ROOT / "src/hub/grid_v2.py"


def _pin_payload():
    return json.loads(PIN_PATH.read_text(encoding="utf-8"))


def _write_pin(tmp_path, payload, name="pin.json"):
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def test_runtime_module_is_byte_identical_to_canonical_template():
    assert RUNTIME_PATH.read_bytes() == TEMPLATE_PATH.read_bytes()


def test_real_thehub_pin_loads_and_emits_identity():
    pin = load_pin(PIN_PATH, expected_consumer="thehub-pr", required_level="L1")
    identity = grid_identity(pin)
    assert identity == {
        "Grid_ID": GRID_ID,
        "Grid_Version": GRID_VERSION,
        "Grid_Level": "L1",
        "CRS": CRS,
        "Grid_Manifest_SHA256": GRID_MANIFEST_SHA256,
        "Cell_Schema_SHA256": CELL_SCHEMA_SHA256,
        "Binding_Schema_SHA256": BINDING_SCHEMA_SHA256,
        "Mask_Schema_SHA256": MASK_SCHEMA_SHA256,
        "Geometry_Authority": "spiderweb-pr",
        "Authority_Commit": AUTHORITY_COMMIT,
    }


@pytest.mark.parametrize(
    ("field", "bad_value", "message"),
    [
        ("grid_id", "PR_GRID_LOGICAL_V1", "grid_id"),
        ("grid_version", "2.0.0", "grid_version"),
        ("grid_manifest_sha256", "0" * 64, "grid_manifest_sha256"),
        ("cell_schema_sha256", "0" * 64, "cell_schema_sha256"),
    ],
)
def test_contract_identity_mismatch_fails_closed(tmp_path, field, bad_value, message):
    payload = _pin_payload()
    payload[field] = bad_value
    with pytest.raises(GridV2PinError, match=message):
        load_pin(
            _write_pin(tmp_path, payload),
            expected_consumer="thehub-pr",
        )


def test_unsupported_level_fails_closed():
    with pytest.raises(GridV2PinError, match="unsupported grid level"):
        load_pin(
            PIN_PATH,
            expected_consumer="thehub-pr",
            required_level="L4",
        )


def test_hash_shape_failure_fails_closed(tmp_path):
    payload = _pin_payload()
    payload["binding_schema_sha256"] = "not-a-sha"
    with pytest.raises(GridV2PinError, match="binding_schema_sha256"):
        load_pin(_write_pin(tmp_path, payload), expected_consumer="thehub-pr")


def test_complete_six_consumer_denominator_validates(tmp_path):
    base = _pin_payload()
    paths = {}
    for consumer, default_level in EXPECTED_DEFAULT_LEVELS.items():
        payload = copy.deepcopy(base)
        payload["consumer"] = consumer
        payload["default_level"] = default_level
        paths[consumer] = _write_pin(
            tmp_path,
            payload,
            name=consumer + ".json",
        )

    validated = validate_pin_set(paths)
    assert set(validated) == set(EXPECTED_DEFAULT_LEVELS)
    assert {
        pin.payload["grid_manifest_sha256"]
        for pin in validated.values()
    } == {GRID_MANIFEST_SHA256}


def test_missing_consumer_is_a_denominator_failure(tmp_path):
    base = _pin_payload()
    paths = {}
    for consumer, default_level in EXPECTED_DEFAULT_LEVELS.items():
        if consumer == "ovnis-pr":
            continue
        payload = copy.deepcopy(base)
        payload["consumer"] = consumer
        payload["default_level"] = default_level
        paths[consumer] = _write_pin(
            tmp_path,
            payload,
            name=consumer + ".json",
        )

    with pytest.raises(GridV2PinError, match="denominator mismatch"):
        validate_pin_set(paths)


@pytest.mark.parametrize(
    "cell_id",
    [
        "PRG2:L0:R066:C0170",
        "PRG2:L1:R133:C0341",
        "PRG2:L2:R267:C0683",
        "PRG2:L3:R535:C1367",
    ],
)
def test_cell_id_accepts_exact_level_bounds(cell_id):
    assert validate_cell_id(cell_id) == cell_id


@pytest.mark.parametrize(
    "cell_id",
    [
        "PRG2:L0:R067:C0000",
        "PRG2:L0:R000:C0171",
        "PRG2:L1:R134:C0000",
        "PRG2:L1:R000:C0342",
        "PRG2:L2:R268:C0000",
        "PRG2:L2:R000:C0684",
        "PRG2:L3:R536:C0000",
        "PRG2:L3:R000:C1368",
        "R0_C0",
        "PRG2:L1:R1:C1",
    ],
)
def test_cell_id_rejects_out_of_range_or_noncanonical(cell_id):
    with pytest.raises(GridV2PinError):
        validate_cell_id(cell_id)


def test_cell_id_level_mismatch_fails_closed():
    with pytest.raises(GridV2PinError, match="does not match requested level"):
        validate_cell_id("PRG2:L2:R000:C0000", level="L1")


def test_grid_identity_can_bind_exact_cell():
    pin = load_pin(PIN_PATH, expected_consumer="thehub-pr")
    identity = grid_identity(
        pin,
        level="L1",
        cell_id="PRG2:L1:R075:C0234",
    )
    assert identity["Cell_ID"] == "PRG2:L1:R075:C0234"
    assert identity["Grid_Level"] == "L1"


def test_attach_grid_identity_preserves_data_state_semantics():
    pin = load_pin(PIN_PATH, expected_consumer="thehub-pr")
    payload = {
        "Record_Count": 0,
        "Data_State": "ZERO_RECORDS",
    }
    stamped = attach_grid_identity(
        payload,
        pin,
        level="L1",
        cell_id="PRG2:L1:R075:C0234",
    )
    assert stamped["Record_Count"] == 0
    assert stamped["Data_State"] == "ZERO_RECORDS"
    assert stamped["Grid_Identity"]["Cell_ID"] == "PRG2:L1:R075:C0234"


def test_build_grid_deep_link_is_canonical_and_url_safe():
    pin = load_pin(PIN_PATH, expected_consumer="thehub-pr")
    path = build_grid_deep_link(
        pin,
        level="L1",
        cell_id="PRG2:L1:R075:C0234",
        base_path="/hub/",
        as_of="2026-10-09T12:00:00-04:00",
    )
    assert path == (
        "/hub/grid/PR_GRID_GEOGRAPHIC_V2/2.0.0-rc1/"
        "L1/PRG2:L1:R075:C0234"
        "?as_of=2026-10-09T12%3A00%3A00-04%3A00"
    )


def test_deep_link_rejects_blank_as_of():
    pin = load_pin(PIN_PATH, expected_consumer="thehub-pr")
    with pytest.raises(GridV2PinError, match="as_of cannot be blank"):
        build_grid_deep_link(
            pin,
            level="L1",
            cell_id="PRG2:L1:R075:C0234",
            as_of=" ",
        )


def test_attach_grid_identity_rejects_conflicting_existing_identity():
    pin = load_pin(PIN_PATH, expected_consumer="thehub-pr")
    with pytest.raises(GridV2PinError, match="conflicting Grid_Identity"):
        attach_grid_identity(
            {"Grid_Identity": {"Grid_ID": "WRONG_GRID"}},
            pin,
            level="L1",
            cell_id="PRG2:L1:R075:C0234",
        )
