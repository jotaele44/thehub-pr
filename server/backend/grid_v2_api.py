"""Read-only PR_GRID_GEOGRAPHIC_V2 Cell_Profile API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from hub.cell_profile_v2 import CellProfileV2Error, build_unmigrated_hub_profile
from hub.grid_v2 import GRID_ID, GRID_VERSION, GridV2PinError, load_pin

router = APIRouter(prefix="/api/grid", tags=["grid-v2"])

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PIN_PATH = _REPO_ROOT / "federation/spatial/pr_grid_geographic_v2.pin.json"


@router.get("/{grid_id}/{grid_version}/{level}/{cell_id}/profile")
def cell_profile_v2(
    grid_id: str,
    grid_version: str,
    level: str,
    cell_id: str,
    as_of: str | None = Query(None, min_length=1, max_length=80),
) -> dict[str, Any]:
    """Return TheHub's truthful V2 profile without inventing pre-migration counts."""
    if grid_id != GRID_ID:
        raise HTTPException(status_code=422, detail=f"unsupported Grid_ID: {grid_id!r}")
    if grid_version != GRID_VERSION:
        raise HTTPException(
            status_code=422,
            detail=f"unsupported Grid_Version: {grid_version!r}",
        )
    try:
        pin = load_pin(
            _PIN_PATH,
            expected_consumer="thehub-pr",
            required_level=level,
        )
        return build_unmigrated_hub_profile(
            pin,
            level=level,
            cell_id=cell_id,
            as_of=as_of,
        )
    except (GridV2PinError, CellProfileV2Error) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
