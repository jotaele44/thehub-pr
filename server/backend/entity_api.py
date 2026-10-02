"""Entity composition API: ``GET /api/entity/{record_id}``.

Read-only. Loads one canonical Entities row and only the rows the store already
links to it: relationship/correlation edges that name it as source or target,
observations/alerts whose ``entity_id`` is it, the entities on the far side of
those edges, and the sources they cite. ``hub.entity_composition`` arranges them;
no matching or inference happens here.
"""

from __future__ import annotations

import json
from contextlib import closing
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Tuple

from fastapi import APIRouter, HTTPException

from hub.entity_composition import (
    ANCHOR_COLLECTION,
    DEFAULT_LINKED_LIMIT,
    DEFAULT_RELATIONSHIP_LIMIT,
    EDGE_COLLECTIONS,
    LINKED_COLLECTIONS,
    compose_entity,
)
from server.backend.evidence_api import _SOURCES_COLLECTION, STORE_BOOKKEEPING_KEYS, _core, _load

router = APIRouter(prefix="/api/entity", tags=["entity"])


def _decode(data: str) -> Dict[str, Any]:
    row = json.loads(data)
    for key in STORE_BOOKKEEPING_KEYS:
        row.pop(key, None)
    return row


def _query(sql: str, params: Tuple[Any, ...]) -> List[Tuple[str, Dict[str, Any]]]:
    with closing(_core()._conn()) as conn:
        return [(r[0], _decode(r[1])) for r in conn.execute(sql, params).fetchall()]


def composition_for(record_id: str, *, now: datetime | None = None) -> Dict[str, Any]:
    anchor = _load(ANCHOR_COLLECTION, [record_id]).get(record_id)
    if anchor is None:
        raise HTTPException(status_code=404, detail=f"{ANCHOR_COLLECTION}/{record_id} not found")

    edge_types = tuple(EDGE_COLLECTIONS)
    edges = _query(
        f"SELECT entity_type, data FROM entities WHERE entity_type IN ({','.join('?' for _ in edge_types)}) "
        "AND (json_extract(data, '$.source_entity_id') = ? OR json_extract(data, '$.target_entity_id') = ?) "
        "ORDER BY entity_type, entity_id LIMIT ?",
        (*edge_types, record_id, record_id, DEFAULT_RELATIONSHIP_LIMIT + 1),
    )
    linked_types = tuple(LINKED_COLLECTIONS)
    linked = _query(
        f"SELECT entity_type, data FROM entities WHERE entity_type IN ({','.join('?' for _ in linked_types)}) "
        "AND json_extract(data, '$.entity_id') = ? ORDER BY entity_type, entity_id LIMIT ?",
        (*linked_types, record_id, DEFAULT_LINKED_LIMIT + 1),
    )

    other_ids = {str(row.get(k)) for _, row in edges for k in ("source_entity_id", "target_entity_id") if row.get(k)}
    other_ids.discard(record_id)
    counterparts: Mapping[str, Mapping[str, Any]] = _load(ANCHOR_COLLECTION, sorted(other_ids))
    cited = [
        str(row.get(k))
        for row in (anchor, *(r for _, r in edges))
        for k in ("source_id", "evidence_source_id")
        if row.get(k)
    ]
    sources = _load(_SOURCES_COLLECTION, cited)
    return compose_entity(
        anchor,
        now=now or datetime.now(timezone.utc),
        edges=edges,
        linked=linked,
        counterparts=counterparts,
        sources=sources,
    )


@router.get("/{record_id}")
def get_entity_composition(record_id: str) -> Dict[str, Any]:
    return composition_for(record_id)
