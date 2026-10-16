"""Profile migration gate: provenance, boundary multiplicity, and no-data semantics."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "federation-templates/spatial"))
from pr_grid_v2_profiles import ProfileError, build_profiles  # noqa: E402
import pr_grid_v2_runtime as grid  # noqa: E402


def _write(path: Path, obj: object) -> Path:
    path.write_text(json.dumps(obj) + "\n", encoding="utf-8")
    return path


def _fixture(tmp_path: Path):
    base = json.loads((ROOT / "federation/spatial/pr_grid_geographic_v2.pin.json").read_text())
    base["consumer"] = "aguayluz-pr"
    base["default_level"] = "L1"
    pin = _write(tmp_path / "pin.json", base)
    cid = "PRG2:L1:R075:C0234"
    binding = {
        "Grid_ID": grid.GRID_ID, "Grid_Version": grid.GRID_VERSION,
        "Grid_Level": "L1", "Cell_ID": cid, "Repository": "aguayluz-pr",
        "Record_ID": "g1", "Binding_Method": "COVERS",
        "Uncertainty_Class": "EXACT", "Binding_State": "EDGE_SHARED",
    }
    bindings = _write(tmp_path / "bindings.jsonl", binding)
    raw = bindings.read_bytes()
    receipt = _write(tmp_path / "binding_receipt.json", {
        "Grid_ID": grid.GRID_ID, "Grid_Version": grid.GRID_VERSION,
        "Grid_Manifest_SHA256": grid.GRID_MANIFEST_SHA256,
        "Binding_Schema_Version": grid.BINDING_SCHEMA_VERSION,
        "Binding_Output_SHA256": hashlib.sha256(raw).hexdigest(),
        "Binding_Output_Bytes": len(raw), "Binding_Row_Count": 1,
    })
    records = _write(tmp_path / "records.jsonl", {
        "Repository": "aguayluz-pr", "Record_ID": "g1", "Category": "gauge"
    })
    coverage = _write(tmp_path / "coverage.json", {
        "Repository": "aguayluz-pr", "Grid_ID": grid.GRID_ID,
        "Grid_Version": grid.GRID_VERSION, "Grid_Level": "L1",
        "Grid_Manifest_SHA256": grid.GRID_MANIFEST_SHA256,
        "Coverage_Manifest_State": "VERIFIED",
        "Coverage_Evidence_SHA256": "a" * 64,
        "Coverage_Cells": ["PRG2:L1:R075:C0235"],
    })
    return {"pin_path": pin, "bindings_path": bindings, "receipt_path": receipt,
            "records_path": records, "coverage_path": coverage, "level": "L1"}


def test_profiles_separate_present_zero_and_absent(tmp_path):
    args = _fixture(tmp_path)
    profiles, receipt = build_profiles(**args, requested_cells=("PRG2:L1:R075:C0236",))
    assert [p["Data_State"] for p in profiles] == ["HAS_RECORDS", "ZERO_RECORDS", "NO_DATA"]
    assert profiles[0]["Record_Count"] == 1
    assert profiles[0]["Shared_Boundary_Record_Count"] == 1
    assert profiles[1]["Record_Count"] == 0
    assert profiles[1]["Coverage_State"] == "VERIFIED"
    assert profiles[2]["Coverage_State"] == "UNKNOWN"
    assert all(p["Geometry_Included"] is False for p in profiles)
    assert all(p["Grid_Identity"]["Grid_Manifest_SHA256"] == grid.GRID_MANIFEST_SHA256 for p in profiles)
    assert receipt["Profile_Count"] == 3


def test_missing_coverage_is_never_true_zero(tmp_path):
    args = _fixture(tmp_path)
    args["coverage_path"] = None
    profiles, _ = build_profiles(**args, requested_cells=("PRG2:L1:R075:C0235",))
    assert profiles[1]["Data_State"] == "NO_DATA"


def test_corrupted_binding_receipt_fails_closed(tmp_path):
    args = _fixture(tmp_path)
    contents = json.loads(args["receipt_path"].read_text())
    contents["Binding_Output_SHA256"] = "0" * 64
    _write(args["receipt_path"], contents)
    with pytest.raises(ProfileError, match="Binding_Output_SHA256"):
        build_profiles(**args)


def test_uncertain_or_misversioned_binding_fails(tmp_path):
    args = _fixture(tmp_path)
    row = json.loads(args["bindings_path"].read_text())
    row["Uncertainty_Class"] = "APPROXIMATE"
    _write(args["bindings_path"], row)
    receipt = json.loads(args["receipt_path"].read_text())
    raw = args["bindings_path"].read_bytes()
    receipt["Binding_Output_SHA256"] = hashlib.sha256(raw).hexdigest()
    receipt["Binding_Output_Bytes"] = len(raw)
    _write(args["receipt_path"], receipt)
    with pytest.raises(ProfileError, match="non-exact"):
        build_profiles(**args)


def _replace_binding(args, row):
    _write(args["bindings_path"], row)
    raw = args["bindings_path"].read_bytes()
    receipt = json.loads(args["receipt_path"].read_text())
    receipt["Binding_Output_SHA256"] = hashlib.sha256(raw).hexdigest()
    receipt["Binding_Output_Bytes"] = len(raw)
    receipt["Binding_Row_Count"] = 1
    _write(args["receipt_path"], receipt)


@pytest.mark.parametrize(
    ("method", "measure_fields"),
    [
        (
            "INTERSECTS_POSITIVE_AREA",
            {"Overlap_Area_m2": 250000.0, "Cell_Coverage_Fraction": 0.25},
        ),
        (
            "LINE_POSITIVE_LENGTH",
            {"Length_In_Cell_m": 500.0},
        ),
    ],
)
def test_exact_geometry_bindings_are_profile_eligible(tmp_path, method, measure_fields):
    args = _fixture(tmp_path)
    row = json.loads(args["bindings_path"].read_text())
    row["Binding_Method"] = method
    row["Binding_State"] = "INTERIOR"
    row.update(measure_fields)
    _replace_binding(args, row)

    profiles, receipt = build_profiles(**args)
    assert profiles[0]["Data_State"] == "HAS_RECORDS"
    assert profiles[0]["Record_Count"] == 1
    assert profiles[0]["Shared_Boundary_Record_Count"] == 0
    assert receipt["Migration_Class"] == "SPIDERWEB_CERTIFIED_EXACT_BINDINGS"
    assert receipt["Accepted_Binding_Methods"] == [
        "COVERS",
        "INTERSECTS_POSITIVE_AREA",
        "LINE_POSITIVE_LENGTH",
    ]


@pytest.mark.parametrize(
    ("method", "uncertainty"),
    [
        ("ADMINISTRATIVE_SET", "ADMINISTRATIVE_ONLY"),
        ("DERIVED_SET", "DERIVED"),
    ],
)
def test_set_bindings_remain_excluded_from_exact_profiles(tmp_path, method, uncertainty):
    args = _fixture(tmp_path)
    row = json.loads(args["bindings_path"].read_text())
    row["Binding_Method"] = method
    row["Uncertainty_Class"] = uncertainty
    row["Binding_State"] = "INTERIOR"
    _replace_binding(args, row)

    with pytest.raises(ProfileError, match="non-exact"):
        build_profiles(**args)


@pytest.mark.parametrize(
    ("method", "fields", "message"),
    [
        (
            "INTERSECTS_POSITIVE_AREA",
            {"Overlap_Area_m2": 0.0, "Cell_Coverage_Fraction": 0.0},
            "positive-area",
        ),
        (
            "LINE_POSITIVE_LENGTH",
            {"Length_In_Cell_m": 0.0},
            "positive-length",
        ),
    ],
)
def test_invalid_exact_geometry_measure_fails_closed(tmp_path, method, fields, message):
    args = _fixture(tmp_path)
    row = json.loads(args["bindings_path"].read_text())
    row["Binding_Method"] = method
    row["Binding_State"] = "INTERIOR"
    row.update(fields)
    _replace_binding(args, row)

    with pytest.raises(ProfileError, match=message):
        build_profiles(**args)
