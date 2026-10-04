"""Spatial API: ``GET /api/spatial/features`` and ``GET /api/spatial/intel``.

Read-only. Serves the Hub-held rows that can be placed on the Property Map
(``hub.spatial_features``): points only where the producer declared a point
precision, plus an account of rows kept off the map and the municipality-level
references they record. Location Intel answers "what does the Hub hold near this
point": rows within a radius, nearest first, with each one's precision. No
producer is called at runtime and nothing is geocoded or inferred here.
"""

from __future__ import annotations

import unicodedata
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from hub import spatial_features as sf
from hub.ingest import STREAM_TO_COLLECTION
from server.backend.entity_api import _query

router = APIRouter(prefix="/api/spatial", tags=["spatial"])

_COLLECTIONS = {STREAM_TO_COLLECTION[stream]: stream for stream in sf.STREAMS}
INTEL_MAX_RESULTS = 200


def spatial_rows() -> List[sf.Row]:
    """Every row of the mappable streams, so rows kept off the map are counted, not dropped."""
    marks = ",".join("?" for _ in _COLLECTIONS)
    rows = _query(f"SELECT entity_type, data FROM entities WHERE entity_type IN ({marks})", tuple(_COLLECTIONS))
    return [(_COLLECTIONS[collection], collection, row) for collection, row in rows]


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return " ".join("".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower().split())


@router.get("/features")
def spatial_features(
    bbox: Optional[str] = Query(None, max_length=120),
    category: Optional[List[str]] = Query(None),
    producer: Optional[List[str]] = Query(None),
    include_synthetic: bool = Query(False),
    limit: int = Query(sf.DEFAULT_LIMIT, ge=1, le=sf.MAX_LIMIT),
) -> Dict[str, Any]:
    try:
        box = sf.parse_bbox(bbox)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return sf.build_features(spatial_rows(), bbox=box, categories=tuple(category or ()),
                             producers=tuple(producer or ()), include_synthetic=include_synthetic, limit=limit)


@router.get("/intel")
def location_intel(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_m: float = Query(1000, ge=10, le=50000),
    municipality: Optional[str] = Query(None, max_length=80),
    include_synthetic: bool = Query(False),
) -> Dict[str, Any]:
    collection = sf.build_features(spatial_rows(), include_synthetic=include_synthetic, limit=sf.MAX_LIMIT)
    near = sf.nearby(collection["features"], lat, lon, radius_m)
    counts: Dict[str, int] = {}
    for item in near:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    wanted = _fold(municipality) if municipality else None
    refs = [ref for ref in collection["area_references"]
            if wanted is not None and _fold(ref["municipality_as_recorded"]) == wanted]
    return {
        "contract": sf.CONTRACT_ID,
        "point": {"lat": lat, "lon": lon},
        "radius_m": radius_m,
        "nearby_total": len(near),
        "nearby": near[:INTEL_MAX_RESULTS],
        "nearby_truncated": len(near) > INTEL_MAX_RESULTS,
        "category_counts": dict(sorted(counts.items())),
        "municipality": municipality,
        "municipality_area_references": refs,
        "distance_basis": "great-circle distance to each mapped point",
    }
