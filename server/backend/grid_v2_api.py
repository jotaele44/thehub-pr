"""Read-only V2 grid handoff and producer Cell_Profile retrieval.

TheHub does not generate geometry or reconstruct producer bindings.
Absent profile materializations are NO_DATA, not ZERO_RECORDS.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from hub.grid_v2 import (
    EXPECTED_CONSUMERS, GRID_ID, GRID_VERSION, GridV2PinError,
    grid_identity, load_pin, validate_cell_id, validate_level,
)

router = APIRouter(tags=["grid-v2"])
ROOT = Path(__file__).resolve().parents[2]
PIN_PATH = ROOT / "federation/spatial/pr_grid_geographic_v2.pin.json"


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
            for raw in path.read_text(encoding="utf-8").splitlines():
                if not raw:
                    continue
                item = json.loads(raw)
                if not isinstance(item, dict):
                    raise ValueError("profile is not a JSON object")
                if item.get("Cell_ID") != validated_id:
                    continue
                if item.get("Repository") != repo or item.get("Grid_Identity") != identity:
                    raise ValueError("mismatched profile identity")
                if item.get("Geometry_Included") is not False:
                    raise ValueError("geometry must remain with Spiderweb")
                if item.get("Data_State") not in ("HAS_RECORDS", "ZERO_RECORDS", "NO_DATA"):
                    raise ValueError("invalid data state")
                profiles.append(item)
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
