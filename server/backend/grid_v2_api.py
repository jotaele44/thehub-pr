"""Read-only V2 grid handoff and producer Cell_Profile retrieval.

TheHub does not generate geometry or reconstruct producer bindings.
Absent profile materializations are NO_DATA, not ZERO_RECORDS.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from jsonschema import Draft202012Validator

from hub.grid_v2 import (
    EXPECTED_CONSUMERS, GRID_ID, GRID_VERSION, GridV2PinError,
    build_grid_deep_link, grid_identity, load_pin, validate_cell_id, validate_level,
)

router = APIRouter(tags=["grid-v2"])
ROOT = Path(__file__).resolve().parents[2]
PIN_PATH = ROOT / "federation/spatial/pr_grid_geographic_v2.pin.json"
PROFILE_SCHEMA_PATH = ROOT / "schemas/cell_profile_v2.schema.json"
PROFILE_TYPES = {
    "aguayluz-pr": "water_hydrology",
    "skywatcher-pr": "flight_activity",
    "ovnis-pr": "anomalous_cases",
    "moneysweep-pr": "financial_activity",
    "centinelas-pr": "monitoring_state",
}


# Frozen schema is resolved once during import; failure blocks the API rather than
# returning partially validated producer profiles.
_PROFILE_SCHEMA = json.loads(PROFILE_SCHEMA_PATH.read_text(encoding="utf-8"))
Draft202012Validator.check_schema(_PROFILE_SCHEMA)
_PROFILE_VALIDATOR = Draft202012Validator(_PROFILE_SCHEMA)


@router.get("/grid/{grid_id}/{grid_version}/{level}/{cell_id}")
@router.get("/api/grid/{grid_id}/{grid_version}/{level}/{cell_id}")
def cell_handoff(
    grid_id: str, grid_version: str, level: str, cell_id: str,
) -> dict[str, Any]:
    """Return one pinned cell and the available domain-owned profile references."""
    if grid_id != GRID_ID or grid_version != GRID_VERSION:
        raise HTTPException(422, "wrong Grid_ID or Grid_Version")
    try:
        selected_level = validate_level(level)
        validated_id = validate_cell_id(cell_id, level=selected_level)
        pin = load_pin(PIN_PATH, expected_consumer="thehub-pr", required_level=level)
        identity = grid_identity(pin, level=level, cell_id=validated_id)
    except GridV2PinError as exc:
        raise HTTPException(503, "grid pin unavailable or incompatible: " + str(exc)) from exc

    root = os.environ.get("PRII_GRID_V2_PROFILE_ROOT")
    if root is None:
        return {
            "Grid_Identity": identity, "Cell_Profile_State": "NO_DATA",
            "Profile_Storage_State": "NOT_CONFIGURED",
            "Profiles": [], "Identity_Default": "CANDIDATE_NOT_IDENTITY",
            "Geometry_Included": False,
        }
    profiles = []
    for repo in sorted(EXPECTED_CONSUMERS - {"thehub-pr"}):
        path = Path(root) / repo / (level + ".jsonl")
        if not path.exists():
            continue
        if path.stat().st_size > 25_000_000:
            raise HTTPException(503, "profile artifact exceeds bounded read size: " + repo)
        try:
            receipt_path = path.with_suffix(".receipt.json")
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            payload = path.read_bytes()
            if (receipt.get("Output_SHA256") != hashlib.sha256(payload).hexdigest()
                    or receipt.get("Repository") != repo
                    or receipt.get("Grid_Identity") != grid_identity(pin, level=level)
                    or receipt.get("Geometry_Copied") is not False
                    or receipt.get("State") != "CANDIDATE_NOT_CANONICAL"):
                raise ValueError("unverified producer profile output receipt")
            seen_cells: set[str] = set()
            valid_rows = 0
            for raw in payload.decode("utf-8").splitlines():
                if not raw:
                    continue
                item = json.loads(raw)
                if not isinstance(item, dict):
                    raise ValueError("profile is not a JSON object")
                errors = list(_PROFILE_VALIDATOR.iter_errors(item))
                if errors:
                    raise ValueError("invalid Cell_Profile 1.2: " + errors[0].message)
                cid = item["Cell_ID"]
                if cid in seen_cells:
                    raise ValueError("duplicate producer Cell_ID")
                seen_cells.add(cid)
                valid_rows += 1
                # Validate every row, not merely the requested Cell_ID. A
                # corrupted neighboring cell invalidates its source artifact.
                if (item.get("Repository") != repo
                        or item.get("Grid_Identity") != grid_identity(
                            pin, level=level, cell_id=cid
                        )):
                    raise ValueError("mismatched profile identity")
                if item.get("Grid_Deep_Link") != build_grid_deep_link(
                    pin, level=level, cell_id=cid
                ):
                    raise ValueError("mismatched profile deep link")
                if item.get("Geometry_Included") is not False:
                    raise ValueError("geometry must remain with Spiderweb")
                if item.get("Profile_Type") != PROFILE_TYPES[repo]:
                    raise ValueError("producer profile type mismatch")
                state = item.get("Data_State")
                count = item.get("Record_Count")
                if state not in ("HAS_RECORDS", "ZERO_RECORDS", "NO_DATA"):
                    raise ValueError("invalid data state")
                if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                    raise ValueError("invalid record count")
                if (state == "HAS_RECORDS") != (count > 0):
                    raise ValueError("data state contradicts record count")
                if state == "ZERO_RECORDS" and item.get("Coverage_State") != "VERIFIED":
                    raise ValueError("zero records requires verified coverage")
                if state == "NO_DATA" and item.get("Coverage_State") != "UNKNOWN":
                    raise ValueError("no data cannot claim verified coverage")
                if item["Shared_Boundary_Record_Count"] > count:
                    raise ValueError("shared boundary count exceeds record count")
                if len(item["Top_Record_IDs"]) > count:
                    raise ValueError("top record ID count exceeds record count")
                if item["Category_Count"] != len(item["Categories"]):
                    raise ValueError("category count contradiction")
                for key in ("Categories", "Binding_Method_Counts", "Uncertainty_Class_Counts"):
                    if sum(item[key].values()) != count:
                        raise ValueError(key + " count contradiction")
                if item["Exact_Record_Count"] + item["Non_Exact_Record_Count"] != count:
                    raise ValueError("exact and non-exact record counts contradict total")
                if cid == validated_id:
                    profiles.append(item)
            if receipt.get("Profile_Count") != valid_rows:
                raise ValueError("profile row denominator mismatch")
        except (OSError, ValueError, TypeError) as exc:
            raise HTTPException(503, "profile validation BLOCKED: " + str(exc)) from exc
    return {
        "Grid_Identity": identity,
        "Cell_Profile_State": "AVAILABLE" if profiles else "NO_DATA",
        "Profile_Storage_State": "CONFIGURED",
        "Profiles": profiles,
        "Identity_Default": "CANDIDATE_NOT_IDENTITY",
        "Geometry_Included": False,
    }
