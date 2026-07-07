"""Ingest a Hub aggregate into the server entity store (``data/hub.db``).

The aggregation pipeline (``hub aggregate`` / ``hub correlate``) writes canonical
JSONL streams to ``data/aggregate/``. The FastAPI server
(``server/backend/main.py``) reads a generic SQLite document store at
``data/hub.db`` and, until now, only ever saw the ``Programs`` rows it seeds from
the registry. Nothing connected the two halves.

This module is that bridge. It loads each aggregate stream into a store
collection keyed by the row's canonical id, so a running server serves the live
federation graph at ``/api/entities/<Collection>`` instead of a static snapshot.

Design notes:

* **Idempotent.** Re-ingesting the same aggregate replaces rows in place
  (``INSERT OR REPLACE`` on the ``(entity_type, entity_id)`` primary key) — no
  duplicates, stable counts.
* **No server process required.** The bridge writes ``data/hub.db`` directly with
  the *same* DDL as ``server/backend/main.py::_init_db``, so the store and this
  bridge can never diverge; the server picks the rows up on its next read.
* **Canonical, lossless.** The full canonical row (including the aggregate's
  ``_producers`` provenance array) is stored verbatim in the JSON ``data`` column;
  only an ``id`` key is injected so the server's read path (which backfills
  ``id`` / ``created_date`` / ``updated_date``) and mutations key off it.

Stream -> collection naming is a single module constant (``STREAM_TO_COLLECTION``)
so the frontend-facing retarget (Phase 2: map onto the UI's per-domain collection
names/fields) is a one-spot edit.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from ._schemas import STREAM_ID_FIELD

# Store DDL — kept byte-identical to server/backend/main.py::_init_db.
_SCHEMA = """
    CREATE TABLE IF NOT EXISTS entities (
        entity_type TEXT NOT NULL,
        entity_id   TEXT NOT NULL,
        data        TEXT NOT NULL,
        updated_at  TEXT NOT NULL,
        PRIMARY KEY (entity_type, entity_id)
    )
"""

# Aggregate stream (file stem) -> store collection name (entity_type).
STREAM_TO_COLLECTION: Dict[str, str] = {
    "sources": "Sources",
    "entities": "Entities",
    "relationships": "Relationships",
    "funding_awards": "FundingAwards",
    "transactions": "Transactions",
    "observations": "Observations",
    "alerts": "Alerts",
    "correlations": "Correlations",
}

# The field holding each stream's deterministic id. correlations.jsonl rows are
# canonical federation_relationship rows, so they key off relationship_id.
_ID_FIELD: Dict[str, str] = {**STREAM_ID_FIELD, "correlations": "relationship_id"}

# graph_summary.json lands as a single row in this collection (Dashboard counts).
_SUMMARY_COLLECTION = "FederationSummary"
_SUMMARY_ID = "graph_summary"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(_SCHEMA)
    conn.commit()


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _upsert(conn: sqlite3.Connection, collection: str, entity_id: str,
            payload: Dict[str, Any], ts: str) -> None:
    """Store one row, mirroring server/backend/main.py::bulk_create semantics."""
    item = dict(payload)
    item["id"] = entity_id
    item.setdefault("created_date", ts)
    item["updated_date"] = ts
    conn.execute(
        "INSERT OR REPLACE INTO entities (entity_type, entity_id, data, updated_at) "
        "VALUES (?,?,?,?)",
        (collection, entity_id, json.dumps(item, sort_keys=True), ts),
    )


def ingest_aggregate(aggregate_dir: str | Path, db_path: str | Path) -> dict:
    """Load a Hub aggregate directory into the SQLite entity store.

    Returns a summary::

        {
          "db": "<db_path>",
          "collections": {"Entities": 12, "Sources": 4, ...},
          "skipped": {"Entities": 0, ...},   # rows missing their canonical id
          "total": 16,
        }

    Streams (and graph_summary.json) that are absent are silently skipped;
    ``total == 0`` signals "nothing to ingest" for the caller.
    """
    agg = Path(aggregate_dir)
    db = Path(db_path)
    db.parent.mkdir(parents=True, exist_ok=True)

    ts = _now()
    collections: Dict[str, int] = {}
    skipped: Dict[str, int] = {}

    conn = sqlite3.connect(db)
    try:
        _ensure_schema(conn)
        for stream, collection in STREAM_TO_COLLECTION.items():
            fpath = agg / f"{stream}.jsonl"
            if not fpath.exists():
                continue
            id_field = _ID_FIELD[stream]
            upserted = 0
            missing = 0
            for row in _read_jsonl(fpath):
                entity_id = row.get(id_field)
                if not entity_id:
                    missing += 1
                    continue
                _upsert(conn, collection, str(entity_id), row, ts)
                upserted += 1
            collections[collection] = upserted
            if missing:
                skipped[collection] = missing

        summary_path = agg / "graph_summary.json"
        if summary_path.exists():
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            _upsert(conn, _SUMMARY_COLLECTION, _SUMMARY_ID, payload, ts)
            collections[_SUMMARY_COLLECTION] = 1

        conn.commit()
    finally:
        conn.close()

    return {
        "db": str(db),
        "collections": collections,
        "skipped": skipped,
        "total": sum(collections.values()),
    }
