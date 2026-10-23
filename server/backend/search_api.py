"""Federated search API: ``GET /api/search``.

Read-only. The index is built from the canonical stream rows the Hub store
already holds (no producer database is copied) and is rebuilt only when the
store's fingerprint changes, i.e. when a collection's row count or latest write
time moves. See ``hub.federated_search`` for the query semantics.
"""

from __future__ import annotations

import json
import threading
from contextlib import closing
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query

from hub.federated_search import DEFAULT_LIMIT, MAX_LIMIT, SEARCH_STREAMS, FederatedSearchIndex, parse_cursor
from hub.ingest import STREAM_TO_COLLECTION
from server.backend.evidence_api import STORE_BOOKKEEPING_KEYS, _core

router = APIRouter(prefix="/api/search", tags=["search"])

_COLLECTIONS: Dict[str, str] = {STREAM_TO_COLLECTION[stream]: stream for stream in SEARCH_STREAMS}
_lock = threading.Lock()
_cache: Dict[str, Any] = {"key": None, "index": None}


def _fingerprint(conn: Any) -> Tuple[Any, ...]:
    placeholders = ",".join("?" for _ in _COLLECTIONS)
    rows = conn.execute(
        f"SELECT entity_type, COUNT(*), MAX(updated_at) FROM entities "
        f"WHERE entity_type IN ({placeholders}) GROUP BY entity_type ORDER BY entity_type",
        tuple(_COLLECTIONS),
    ).fetchall()
    return tuple((r[0], r[1], r[2]) for r in rows)


def _rows(conn: Any) -> List[Tuple[str, str, Dict[str, Any]]]:
    placeholders = ",".join("?" for _ in _COLLECTIONS)
    out: List[Tuple[str, str, Dict[str, Any]]] = []
    for r in conn.execute(
        f"SELECT entity_type, data FROM entities WHERE entity_type IN ({placeholders})", tuple(_COLLECTIONS)
    ):
        data = json.loads(r[1])
        for key in STORE_BOOKKEEPING_KEYS:
            data.pop(key, None)
        out.append((_COLLECTIONS[r[0]], r[0], data))
    return out


def current_index() -> FederatedSearchIndex:
    core = _core()
    with closing(core._conn()) as conn:
        key = (str(core.DB_PATH), _fingerprint(conn))
        with _lock:
            if _cache["key"] != key:
                _cache["index"] = FederatedSearchIndex.build(_rows(conn))
                _cache["key"] = key
            return _cache["index"]


@router.get("")
def search(
    q: str = Query("", max_length=256),
    type: str = Query("ALL"),
    include_synthetic: bool = Query(False),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    cursor: Optional[str] = Query(None, max_length=12),
) -> Dict[str, Any]:
    try:
        offset = parse_cursor(cursor)
        return current_index().search(
            q, kind=type.upper(), include_synthetic=include_synthetic, limit=limit, offset=offset
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
