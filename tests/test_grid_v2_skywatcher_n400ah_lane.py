"""Evidence gate for the rights-blocked Skywatcher N400AH Grid V2 lane."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANE_PATH = ROOT / "registry/spatial/v2/lanes/skywatcher_n400ah_l2.json"


def _lane() -> dict:
    return json.loads(LANE_PATH.read_text(encoding="utf-8"))


def test_n400ah_lane_preserves_grid_identity_and_rights_blocker():
    lane = _lane()
    assert lane["Schema_Version"] == "pr-grid-v2-domain-lane/1.0"
    assert lane["Lane_ID"] == "SKYWATCHER_N400AH_L2_V2"
    assert lane["State"] == "FROZEN_BLOCKED_RECEIPT"
    assert lane["Producer"] == "skywatcher-pr"
    assert lane["Domain"] == "flight_activity"
    assert lane["Grid_Level"] == "L2"
    assert lane["Grid_ID"] == "PR_GRID_GEOGRAPHIC_V2"
    assert lane["Grid_Version"] == "2.0.0-rc1"
    assert (
        lane["Grid_Authority_Commit"]
        == "0c66e13d14232c0d7cbcbc179b3655904777dc71"
    )
    assert (
        lane["Grid_Manifest_SHA256"]
        == "8902af188ad449955119016f5747fe2393c582d9ed552fb03bcaecd9ab510aa4"
    )
    assert lane["Geometry_Producer"] == "spiderweb-pr"
    assert lane["Consumer_Geometry_Mode"] == "REFERENCE_ONLY"
    assert lane["Expected_Output_State"] == "CANDIDATE_NOT_CANONICAL"

    rights = lane["Rights_Gate"]
    assert rights["Provider_Source_Redistribution_State"] == "UNVERIFIED"
    assert rights["Raw_Provider_Payloads_Committed"] is False
    assert rights["Derived_Coordinate_Rows_Committed"] is False
    assert rights["Per_Cell_Aggregate_Committed"] is False
    assert rights["Public_Authority_Execution_Permitted"] is False
    assert lane["Promotion_Blocker_ID"] == "SKYWATCHER-N400AH-RIGHTS-001"


def test_n400ah_local_recomputation_closes_without_promotion():
    lane = _lane()
    observed = lane["Observed"]
    assert observed["Local_Recomputation_State"] == "PASS"
    assert (
        observed["Execution_Class"]
        == "INDEPENDENT_NUMERIC_RECOMPUTATION_NOT_AUTHORITY_EXECUTION"
    )
    assert observed["Authority_Execution_State"] == "NOT_EXECUTED"
    assert (
        observed["CI_Reproducibility_State"]
        == "BLOCKED_REDISTRIBUTION_RIGHTS_UNVERIFIED"
    )
    assert observed["Input_Record_Count"] == 12_455
    assert observed["Interior_Record_Count"] == 10_875
    assert observed["Outside_Record_Count"] == 1_580
    assert observed["Edge_Shared_Record_Count"] == 0
    assert observed["Corner_Shared_Record_Count"] == 0
    assert observed["Binding_Row_Count"] == 10_875
    assert observed["Boundary_Snap_Record_Count"] == 0
    assert observed["Unique_Bound_L2_Cell_Count"] == 3_211
    assert observed["Interior_Record_Count"] + observed["Outside_Record_Count"] == observed["Input_Record_Count"]
    assert observed["Row_Conservation_State"] == "PASS"
    assert observed["Geometry_Copied"] is False
    assert observed["Candidate_State"] == "CANDIDATE_NOT_CANONICAL"


def test_n400ah_source_identity_is_not_overclaimed():
    lane = _lane()
    source = lane["Source_Identity"]
    assert source["Original_Source_Archive"]["Byte_Identity_State"] == "UNRESOLVED"
    assert source["Recovery_Container"]["Container_Comparison_State"] == "DISTINCT_PAYLOADS"
    subset = source["Frozen_Provider_Subset"]
    assert subset["Member_Count"] == 50
    assert subset["Provider_CSV"] == 25
    assert subset["Provider_KML"] == 25
    assert subset["Member_Identity_State"] == "PASS_BYTE_IDENTICAL_SUBSET"
    assert subset["Missing_Members"] == 0
    assert subset["Divergent_Members"] == 0


def test_n400ah_public_execution_policy_forbids_coordinate_publication():
    lane = _lane()
    policy = lane["Public_Execution_Policy"]
    assert set(policy["Allowed"]) == {
        "receipt_metadata",
        "hash_ledgers",
        "count_closure",
        "state_classification",
    }
    assert {
        "raw_provider_payloads",
        "derived_coordinate_rows",
        "per_cell_track_aggregates",
        "public_spiderweb_authority_binding_artifacts",
    } <= set(policy["Prohibited_Until_Rights_Verified"])
