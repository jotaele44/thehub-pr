"""Grid V2 immutable snapshot and profile contract regression gates."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "registry/spatial/v2/consumer_commit_snapshot.json"
SCHEMA = ROOT / "schemas/cell_profile_v2.schema.json"
CI = ROOT / ".github/workflows/ci.yml"
AUTHORITY_CI = ROOT / ".github/workflows/grid-v2-federation-authority.yml"


def test_exact_consumer_checkouts_not_mutable_main():
    snapshot = json.loads(SNAPSHOT.read_text())
    commits = snapshot["Consumer_Commits"]
    assert len(commits) == 6
    assert set(commits) == {
        "aguayluz-pr", "skywatcher-pr", "ovnis-pr",
        "moneysweep-pr", "centinelas-pr", "thehub-pr",
    }
    assert snapshot["Certification"] == "WITHHELD"
    assert snapshot["Deployment"] == "WITHHELD"
    ci = CI.read_text()
    authority_ci = AUTHORITY_CI.read_text()
    for repo, revision in commits.items():
        assert re.fullmatch(r"[0-9a-f]{40}", revision)
        if repo == "thehub-pr":
            continue
        assert f"repository: jotaele44/{repo}, ref: {revision}," in ci
        assert f'"{repo}:{revision}"' in authority_ci
    authority = snapshot["Authority_Grid_Commit"]
    assert re.fullmatch(r"[0-9a-f]{40}", authority)
    assert f"repository: jotaele44/spiderweb-pr, ref: {authority}," in ci
    assert f'authority_sha="{authority}"' in authority_ci
    assert snapshot["Authority_Main_Observed"] != authority


def _example_profile():
    cid = "PRG2:L1:R075:C0234"
    identity = {
        "Grid_ID": "PR_GRID_GEOGRAPHIC_V2",
        "Grid_Version": "2.0.0-rc1",
        "Grid_Level": "L1",
        "CRS": "EPSG:6566",
        "Grid_Manifest_SHA256": "8902af188ad449955119016f5747fe2393c582d9ed552fb03bcaecd9ab510aa4",
        "Cell_Schema_SHA256": "1c173aee4b21b9baa545b656735155f2236a87c436d467a12132ef53b2592f5d",
        "Binding_Schema_SHA256": "dabc461e47134b3b150be9aeb23b3d0097563493b33b3187538255e06b16a022",
        "Mask_Schema_SHA256": "0b31b717d274b19686bf7f47edbabdaec31c86800f2ca7f1e73ffb663600978b",
        "Geometry_Authority": "spiderweb-pr",
        "Authority_Commit": "0c66e13d14232c0d7cbcbc179b3655904777dc71",
        "Cell_ID": cid,
    }
    return {
        "Schema_Version": "pr-grid-v2-cell-profile/1.2",
        "Grid_Identity": identity,
        "Repository": "aguayluz-pr",
        "Profile_Type": "water_hydrology",
        "Cell_ID": cid,
        "Grid_Deep_Link": f"/grid/PR_GRID_GEOGRAPHIC_V2/2.0.0-rc1/L1/{cid}",
        "Data_State": "HAS_RECORDS",
        "Coverage_State": "UNKNOWN",
        "Record_Count": 2,
        "Category_Count": 1,
        "Categories": {"gauge": 2},
        "Top_Record_IDs": ["g1", "g2"],
        "Binding_Method_Counts": {"COVERS": 2},
        "Uncertainty_Class_Counts": {"EXACT": 2},
        "Exact_Record_Count": 2,
        "Non_Exact_Record_Count": 0,
        "Shared_Boundary_Record_Count": 0,
        "Migration_Class": "RECOMPUTED_FROM_SOURCE_COORDINATE",
        "Identity_Default": "CANDIDATE_NOT_IDENTITY",
        "Geometry_Included": False,
    }


def _validator():
    schema = json.loads(SCHEMA.read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_profile_12_matches_frozen_json_schema():
    v = _validator()
    assert not list(v.iter_errors(_example_profile()))


@pytest.mark.parametrize("mutation", [
    {"Schema_Version": "pr-grid-v2-cell-profile/1.0"},
    {"Geometry_Included": True},
    {"Record_Count": -1},
    {"Migration_Class": "INFERRED"},
    {"Grid_Deep_Link": "/grid/WRONG"},
])
def test_profile_12_rejects_invalid_payload(mutation):
    p = _example_profile()
    p.update(mutation)
    assert list(_validator().iter_errors(p))


def test_profile_12_rejects_wrong_authority_and_missing_counts():
    p = _example_profile()
    p["Grid_Identity"]["Authority_Commit"] = "f" * 40
    assert list(_validator().iter_errors(p))
    p = _example_profile()
    del p["Exact_Record_Count"]
    assert list(_validator().iter_errors(p))


def test_profile_denominator_arithmetic_fixture():
    p = _example_profile()
    assert p["Record_Count"] == p["Exact_Record_Count"] + p["Non_Exact_Record_Count"]
    assert p["Record_Count"] == sum(p["Categories"].values())
    assert p["Record_Count"] == sum(p["Binding_Method_Counts"].values())
    assert p["Record_Count"] == sum(p["Uncertainty_Class_Counts"].values())
