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

from hub.grid_v2 import (
    EXPECTED_CONSUMERS,
    GRID_ID,
    GRID_VERSION,
    GridV2PinError,
    grid_identity,
    load_pin,
    validate_cell_id,
    validate_level,
)

router = APIRouter(tags=["grid-v2"])
ROOT = Path(__file__).resolve().parents[2]
PIN_PATH = ROOT / "federation/spatial/pr_grid_geographic_v2.pin.json"
PROFILE_VERSION = "pr-grid-v2-cell-profile/1.2"
DOMAIN_PROFILE_TYPES = {
    "aguayluz-pr": "water_hydrology",
    "skywatcher-pr": "flight_activity",
    "ovnis-pr": "anomalous_cases",
    "moneysweep-pr": "financial_activity",
    "centinelas-pr": "monitoring_state",
}
PROFILE_FIELDS = {
    "Schema_Version",
    "Grid_Identity",
    "Repository",
    "Profile_Type",
    "Cell_ID",
    "Data_State",
    "Coverage_State",
    "Record_Count",
    "Category_Count",
    "Categories",
    "Top_Record_IDs",
    "Shared_Boundary_Record_Count",
    "Identity_Default",
    "Geometry_Included",
}


def _validate_profile(
    item: object,
    *,
    repository: str,
    identity: dict[str, str],
) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("profile is not a JSON object")
    if set(item) != PROFILE_FIELDS:
        missing = sorted(PROFILE_FIELDS - set(item))
        extra = sorted(set(item) - PROFILE_FIELDS)
        raise ValueError(f"profile field mismatch: missing={missing} extra={extra}")
    if item.get("Schema_Version") != PROFILE_VERSION:
        raise ValueError("stale or unsupported Cell_Profile schema version")
    if item.get("Repository") != repository:
        raise ValueError("mismatched profile repository")
    if item.get("Profile_Type") != DOMAIN_PROFILE_TYPES[repository]:
        raise ValueError("mismatched profile type")
    if item.get("Grid_Identity") != identity:
        raise ValueError("mismatched profile identity")
    if item.get("Cell_ID") != identity["Cell_ID"]:
        raise ValueError("mismatched Cell_ID")
    if item.get("Geometry_Included") is not False:
        raise ValueError("geometry must remain with Spiderweb")
    if item.get("Identity_Default") != "CANDIDATE_NOT_IDENTITY":
        raise ValueError("invalid identity default")

    state = item.get("Data_State")
    coverage = item.get("Coverage_State")
    count = item.get("Record_Count")
    category_count = item.get("Category_Count")
    categories = item.get("Categories")
    top_ids = item.get("Top_Record_IDs")
    shared = item.get("Shared_Boundary_Record_Count")

    if state not in ("HAS_RECORDS", "ZERO_RECORDS", "NO_DATA"):
        raise ValueError("invalid data state")
    if coverage not in ("VERIFIED", "UNKNOWN"):
        raise ValueError("invalid coverage state")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise ValueError("invalid record count")
    if (
        not isinstance(category_count, int)
        or isinstance(category_count, bool)
        or category_count < 0
    ):
        raise ValueError("invalid category count")
    if not isinstance(categories, dict):
        raise ValueError("invalid categories")
    for key, value in categories.items():
        if (
            not isinstance(key, str)
            or not key
            or not isinstance(value, int)
            or isinstance(value, bool)
            or value < 1
        ):
            raise ValueError("invalid category entry")
    if category_count != len(categories) or sum(categories.values()) != count:
        raise ValueError("category counts do not close to record count")
    if (
        not isinstance(top_ids, list)
        or len(top_ids) > 25
        or len(top_ids) != len(set(top_ids))
        or any(not isinstance(value, str) or not value for value in top_ids)
    ):
        raise ValueError("invalid Top_Record_IDs")
    if (
        not isinstance(shared, int)
        or isinstance(shared, bool)
        or shared < 0
        or shared > count
    ):
        raise ValueError("invalid shared-boundary count")

    if state == "HAS_RECORDS":
        if count <= 0:
            raise ValueError("HAS_RECORDS requires positive record count")
    elif count != 0:
        raise ValueError("zero/no-data states require zero record count")

    if state == "ZERO_RECORDS" and coverage != "VERIFIED":
        raise ValueError("ZERO_RECORDS requires verified coverage")
    if state == "NO_DATA" and coverage != "UNKNOWN":
        raise ValueError("NO_DATA requires unknown coverage")

    return item


@router.get("/grid/{grid_id}/{grid_version}/{level}/{cell_id}")
@router.get("/api/grid/{grid_id}/{grid_version}/{level}/{cell_id}")
def cell_handoff(
    grid_id: str,
    grid_version: str,
    level: str,
    cell_id: str,
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
        raise HTTPException(
            503,
            "grid pin unavailable or incompatible: " + str(exc),
        ) from exc

    root = os.environ.get("PRII_GRID_V2_PROFILE_ROOT")
    if root is None:
        return {
            "Grid_Identity": identity,
            "Cell_Profile_State": "NO_DATA",
            "Profile_Storage_State": "NOT_CONFIGURED",
            "Profiles": [],
            "Identity_Default": "CANDIDATE_NOT_IDENTITY",
            "Geometry_Included": False,
        }

    profiles = []
    for repo in sorted(EXPECTED_CONSUMERS - {"thehub-pr"}):
        path = Path(root) / repo / (level + ".jsonl")
        if not path.exists():
            continue
        if path.stat().st_size > 25_000_000:
            raise HTTPException(
                503,
                "profile artifact exceeds bounded read size: " + repo,
            )
        try:
            receipt_path = path.with_suffix(".receipt.json")
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            payload = path.read_bytes()
            if (
                receipt.get("Output_SHA256") != hashlib.sha256(payload).hexdigest()
                or receipt.get("Repository") != repo
                or receipt.get("Grid_Identity") != grid_identity(pin, level=level)
                or receipt.get("Geometry_Copied") is not False
                or receipt.get("State") != "CANDIDATE_NOT_CANONICAL"
            ):
                raise ValueError("unverified producer profile output receipt")
            for raw in payload.decode("utf-8").splitlines():
                if not raw:
                    continue
                item = json.loads(raw)
                if not isinstance(item, dict) or item.get("Cell_ID") != validated_id:
                    continue
                profiles.append(
                    _validate_profile(
                        item,
                        repository=repo,
                        identity=identity,
                    )
                )
        except (OSError, ValueError, TypeError) as exc:
            raise HTTPException(
                503,
                "profile validation BLOCKED: " + str(exc),
            ) from exc

    return {
        "Grid_Identity": identity,
        "Cell_Profile_State": "AVAILABLE" if profiles else "NO_DATA",
        "Profile_Storage_State": "CONFIGURED",
        "Profiles": profiles,
        "Identity_Default": "CANDIDATE_NOT_IDENTITY",
        "Geometry_Included": False,
    }
