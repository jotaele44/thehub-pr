"""Fail-closed PR_GRID_GEOGRAPHIC_V2 Cell_Profile API.

TheHub is the federation control plane, not the geometry authority. This API
serves only explicit CellProfiles already materialized into the Hub store.
Absence is NO_DATA. It never infers record-to-cell membership from coordinates,
municipalities, or other domain fields.
"""

from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path
from typing import Any, Mapping, Optional

from fastapi import APIRouter, HTTPException, Query

from hub.grid_v2 import (
    GRID_ID,
    GRID_VERSION,
    GridV2Pin,
    GridV2PinError,
    build_grid_deep_link,
    grid_identity,
    load_pin,
    validate_cell_id,
    validate_level,
)
from server.backend.evidence_api import STORE_BOOKKEEPING_KEYS, _core

router = APIRouter(prefix="/grid", tags=["grid-v2"])

REPO_ROOT = Path(__file__).resolve().parents[2]
PIN_PATH = REPO_ROOT / "federation/spatial/pr_grid_geographic_v2.pin.json"
CELL_PROFILE_COLLECTION = "CellProfiles"
CONTRACT_ID = "FEDERATION_CELL_PROFILE_V2"
_ALLOWED_DATA_STATES = {
    "NO_DATA",
    "ZERO_RECORDS",
    "NOT_APPLICABLE",
    "UNKNOWN",
    "STALE",
    "DATA_PRESENT",
}


def _pin() -> GridV2Pin:
    try:
        return load_pin(PIN_PATH, expected_consumer="thehub-pr")
    except GridV2PinError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"PR grid V2 authority pin is incompatible: {exc}",
        ) from exc


def _decode(data: str) -> dict[str, Any]:
    payload = json.loads(data)
    for key in STORE_BOOKKEEPING_KEYS:
        payload.pop(key, None)
    return payload


def _profile_rows(cell_id: str) -> list[dict[str, Any]]:
    with closing(_core()._conn()) as conn:
        rows = conn.execute(
            "SELECT data FROM entities WHERE entity_type=? "
            "AND json_extract(data, '$.Grid_Identity.Cell_ID')=? "
            "ORDER BY entity_id",
            (CELL_PROFILE_COLLECTION, cell_id),
        ).fetchall()
    return [_decode(row[0]) for row in rows]


def _validate_profile(
    profile: Mapping[str, Any],
    *,
    pin: GridV2Pin,
    level: str,
    cell_id: str,
) -> dict[str, Any]:
    expected_identity = grid_identity(pin, level=level, cell_id=cell_id)
    observed_identity = profile.get("Grid_Identity")
    if observed_identity != expected_identity:
        raise HTTPException(
            status_code=500,
            detail="stored Cell_Profile has stale or incompatible Grid_Identity",
        )

    repository = profile.get("Repository")
    domain = profile.get("Domain")
    if not isinstance(repository, str) or not repository:
        raise HTTPException(status_code=500, detail="stored Cell_Profile missing Repository")
    if not isinstance(domain, str) or not domain:
        raise HTTPException(status_code=500, detail="stored Cell_Profile missing Domain")

    state = profile.get("Data_State")
    if state not in _ALLOWED_DATA_STATES:
        raise HTTPException(
            status_code=500,
            detail=f"stored Cell_Profile has invalid Data_State: {state!r}",
        )

    count = profile.get("Record_Count")
    if state == "ZERO_RECORDS":
        if count != 0:
            raise HTTPException(
                status_code=500,
                detail="ZERO_RECORDS requires Record_Count=0",
            )
    elif state == "NO_DATA":
        if count is not None:
            raise HTTPException(
                status_code=500,
                detail="NO_DATA requires Record_Count=null",
            )
    elif state == "DATA_PRESENT":
        if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
            raise HTTPException(
                status_code=500,
                detail="DATA_PRESENT requires Record_Count>0",
            )

    return dict(profile)


@router.get("/{grid_id}/{grid_version}/{level}/{cell_id}")
def cell_profile(
    grid_id: str,
    grid_version: str,
    level: str,
    cell_id: str,
    as_of: Optional[str] = Query(None, max_length=128),
) -> dict[str, Any]:
    """Return materialized domain profiles for one canonical V2 cell."""
    # FastAPI injects Query defaults during HTTP requests, but direct contract tests
    # call this function as ordinary Python. Normalize the unapplied Query object
    # to its semantic default so API and direct-call behavior remain identical.
    effective_as_of = as_of if isinstance(as_of, str) else None
    pin = _pin()

    if grid_id != GRID_ID:
        raise HTTPException(status_code=409, detail=f"unsupported Grid_ID: {grid_id}")
    if grid_version != GRID_VERSION:
        raise HTTPException(
            status_code=409,
            detail=f"unsupported Grid_Version: {grid_version}",
        )

    try:
        selected_level = validate_level(level)
        validated_cell = validate_cell_id(cell_id, level=selected_level)
        identity = grid_identity(
            pin,
            level=selected_level,
            cell_id=validated_cell,
        )
        deep_link = build_grid_deep_link(
            pin,
            level=selected_level,
            cell_id=validated_cell,
            as_of=effective_as_of,
        )
    except GridV2PinError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    profiles = [
        _validate_profile(
            row,
            pin=pin,
            level=selected_level,
            cell_id=validated_cell,
        )
        for row in _profile_rows(validated_cell)
    ]

    if not profiles:
        return {
            "contract": CONTRACT_ID,
            "Profile_Availability": "NO_DATA",
            "Grid_Identity": identity,
            "Deep_Link": deep_link,
            "Profiles": [],
            "Profile_Count": 0,
            "note": (
                "No materialized CellProfiles exist for this cell. "
                "NO_DATA is not ZERO_RECORDS."
            ),
        }

    return {
        "contract": CONTRACT_ID,
        "Profile_Availability": "MATERIALIZED",
        "Grid_Identity": identity,
        "Deep_Link": deep_link,
        "Profiles": profiles,
        "Profile_Count": len(profiles),
    }
