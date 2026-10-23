"""Evidence Object API: the provenance inspector's read-only backend.

``GET /api/evidence/{collection}/{record_id}`` projects one federation stream
row held in the Hub store into a FEDERATION_EVIDENCE_OBJECT_V1 view (see
``hub.evidence_object``). The row is read verbatim from the store; only the
sources it cites are looked up, so the endpoint never loads a whole collection.
The projection is recomputed per request against the current time because
temporal state is time-dependent; nothing is written back.
"""

from __future__ import annotations

import json
from contextlib import closing
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

from fastapi import APIRouter, HTTPException

from hub.evidence_object import project_evidence_object
from hub.ingest import STREAM_TO_COLLECTION

router = APIRouter(prefix="/api/evidence", tags=["evidence"])

# Store collection -> federation stream (the inverse of hub.ingest's mapping).
COLLECTION_TO_STREAM: Dict[str, str] = {collection: stream for stream, collection in STREAM_TO_COLLECTION.items()}
_SOURCES_COLLECTION = STREAM_TO_COLLECTION["sources"]
# Keys hub.ingest._upsert adds to every stored row; stripped so the Evidence
# Object (and its row_sha256) describes the producer's canonical row, not the store.
STORE_BOOKKEEPING_KEYS = ("id", "created_date", "updated_date")


def _core() -> Any:
    # Resolved lazily: main.py mounts this router before aliasing itself to the
    # core module, and tests monkeypatch the core's DB_PATH at request time.
    from server.backend import main_core

    return main_core


def _load(collection: str, record_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    ids = [i for i in dict.fromkeys(record_ids) if i]
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    with closing(_core()._conn()) as conn:
        rows = conn.execute(
            f"SELECT entity_id, data FROM entities WHERE entity_type=? AND entity_id IN ({placeholders})",
            (collection, *ids),
        ).fetchall()
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        data = json.loads(r["data"])
        for key in STORE_BOOKKEEPING_KEYS:
            data.pop(key, None)
        out[str(r["entity_id"])] = data
    return out


def evidence_for(collection: str, record_id: str, *, now: Optional[datetime] = None) -> Dict[str, Any]:
    stream = COLLECTION_TO_STREAM.get(collection)
    if stream is None:
        raise HTTPException(status_code=404, detail=f"{collection!r} is not a federation evidence collection")
    row = _load(collection, [record_id]).get(record_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"{collection}/{record_id} not found")
    cited = [str(row.get(k)) for k in ("source_id", "evidence_source_id") if row.get(k)]
    sources: Mapping[str, Mapping[str, Any]] = (
        {record_id: row} if stream == "sources" else _load(_SOURCES_COLLECTION, cited)
    )
    return project_evidence_object(stream, row, now=now or datetime.now(timezone.utc), sources_index=sources)


@router.get("/{collection}/{record_id}")
def get_evidence_object(collection: str, record_id: str) -> Dict[str, Any]:
    return evidence_for(collection, record_id)
