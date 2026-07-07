"""Ingest a Hub aggregate into the server entity store (``data/hub.db``).

The aggregation pipeline (``hub aggregate`` / ``hub correlate``) writes canonical
JSONL streams to ``data/aggregate/``. The FastAPI server
(``server/backend/main.py``) reads a generic SQLite document store at
``data/hub.db`` and serves it at ``/api/entities/<Collection>``; the React UI
reads those collections. This module is the bridge between the two.

The UI was built against per-domain collection names (``UnifiedSources``,
``GraphNodes``/``GraphEdges``, ``GovernanceAlerts``, ``CrossoverLinks``) whose
field names differ from the domain-agnostic canonical streams. So each stream is
run through a small **adapter**: it keeps the full canonical payload (including
the aggregate's ``_producers`` provenance) and *adds* the UI's field names on
top, storing the result under the UI collection name. Streams the UI has no
distinct page for yet are stored under their canonical name unchanged.

Design notes:

* **Idempotent.** Rows upsert by ``(entity_type, entity_id)`` (``INSERT OR
  REPLACE``) — re-ingesting the same aggregate is a no-op on counts.
* **No server process required.** Writes ``data/hub.db`` with the same DDL as
  ``server/backend/main.py::_init_db``; the server picks rows up on its next read.
* **Single source of mapping truth.** ``COLLECTION_ADAPTERS`` is the one place the
  stream -> collection + field projection is defined.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, NamedTuple, Optional

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

# graph_summary.json lands as a single row in this collection.
_SUMMARY_COLLECTION = "FederationSummary"
_SUMMARY_ID = "graph_summary"


# ── projection helpers ──────────────────────────────────────────────────────────

def _band(value: Any) -> Optional[str]:
    """Bucket a 0..1 confidence into the UI's Low/Medium/High select values."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v < 0.5:
        return "Low"
    if v < 0.8:
        return "Medium"
    return "High"


def _first_producer(row: Dict[str, Any]) -> Optional[str]:
    producers = row.get("_producers")
    if isinstance(producers, list) and producers:
        return str(producers[0])
    return None


def _loc(row: Dict[str, Any], key: str) -> Any:
    loc = row.get("location")
    return loc.get(key) if isinstance(loc, dict) else None


def _clean(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Drop keys whose value is None so we never overwrite with nulls."""
    return {k: v for k, v in fields.items() if v is not None}


# program_id -> UI module display name (matches server/frontend/src/lib/federation.js).
_MODULE_NAMES = {
    "spiderweb-pr": "Spiderweb-PR",
    "ovnis-pr": "Ovnis-PR",
    "aguayluz-pr": "AguaYLuz-PR",
    "moneysweep-pr": "MoneySweep-PR",
    "skywatcher-pr": "Skywatcher-PR",
    "centinelas-pr": "Centinelas-PR",
}

# Canonical federation_alert.status -> the UI's GovernanceAlerts review_status.
# The panel treats only {"Open","Acknowledged"} as open, so live producer alerts
# must be translated or they render as closed/hidden. Unknown -> "Open" (surface it).
_ALERT_STATUS = {
    "draft": "Open",
    "active": "Open",
    "validated": "Acknowledged",
    "closed": "Closed",
    "rejected": "Rejected",
}


def _module_for(program_id: Optional[str]) -> Optional[str]:
    if not program_id:
        return None
    return _MODULE_NAMES.get(program_id, program_id)


def _entity_module_map(agg: Path) -> Dict[str, str]:
    """entity_id -> UI module display name, from each entity's first producer.

    correlations.jsonl rows carry only entity ids; the crossover UI needs the
    source/target *modules* to build matrix pairs and chips. Entities do carry
    ``_producers``, so we join on them here."""
    path = agg / "entities.jsonl"
    if not path.exists():
        return {}
    mapping: Dict[str, str] = {}
    for row in _read_jsonl(path):
        eid = row.get("entity_id")
        module = _module_for(_first_producer(row))
        if eid and module:
            mapping[eid] = module
    return mapping


# ── stream -> UI collection field projections ───────────────────────────────────

def _sources_to_unified(row: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    return _clean({
        "source_id": row.get("source_id"),
        "title": row.get("source_name"),
        "source_type": row.get("source_type"),
        "url": row.get("source_url") or row.get("source_ref"),
        "program_id": _first_producer(row),
    })


def _entities_to_nodes(row: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    return _clean({
        "node_id": row.get("entity_id"),
        "label": row.get("name"),
        "node_type": row.get("entity_type"),
        "municipality": _loc(row, "municipality"),
        "latitude": _loc(row, "lat"),
        "longitude": _loc(row, "lon"),
        "confidence": _band(row.get("confidence")),
        "program_id": _first_producer(row),
    })


def _relationships_to_edges(row: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    return _clean({
        "edge_id": row.get("relationship_id"),
        "source_node_id": row.get("source_entity_id"),
        "target_node_id": row.get("target_entity_id"),
        "relationship_type": row.get("relationship_type"),
        "confidence": _band(row.get("confidence")),
    })


def _alerts_to_governance(row: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    attrs = row.get("attributes")
    attributes = attrs if isinstance(attrs, dict) else {}
    status = row.get("status")
    review_status = _ALERT_STATUS.get(status, "Open") if isinstance(status, str) else "Open"
    return _clean({
        "module": row.get("module"),
        "entity_name": row.get("module"),
        "severity": row.get("severity"),
        "review_status": review_status,
        "occurred_at": row.get("observed_at"),
        "record_id": row.get("entity_id"),
        "summary": attributes.get("summary") or row.get("alert_type"),
    })


def _correlations_to_crossover(row: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    entity_module = ctx.get("entity_module", {})
    return _clean({
        "crossover_id": row.get("relationship_id"),
        "source_record_id": row.get("source_entity_id"),
        "target_record_id": row.get("target_entity_id"),
        "source_module": entity_module.get(row.get("source_entity_id")),
        "target_module": entity_module.get(row.get("target_entity_id")),
        "correlation_type": row.get("relationship_type"),
        "confidence_score": row.get("confidence"),
        "confidence_band": _band(row.get("confidence")),
        "rationale": row.get("explanation"),
        "status": "PendingReview",
        "source_ids": [row["source_id"]] if row.get("source_id") else [],
        "created_from": "hub_correlate",
    })


class Adapter(NamedTuple):
    stream: str
    collection: str
    id_field: str
    project: Optional[Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]]


# The one place the stream -> collection + field mapping lives.
# correlations.jsonl rows are canonical federation_relationship rows -> relationship_id.
COLLECTION_ADAPTERS: List[Adapter] = [
    Adapter("sources", "UnifiedSources", STREAM_ID_FIELD["sources"], _sources_to_unified),
    Adapter("entities", "GraphNodes", STREAM_ID_FIELD["entities"], _entities_to_nodes),
    Adapter("relationships", "GraphEdges", STREAM_ID_FIELD["relationships"], _relationships_to_edges),
    Adapter("alerts", "GovernanceAlerts", STREAM_ID_FIELD["alerts"], _alerts_to_governance),
    Adapter("correlations", "CrossoverLinks", "relationship_id", _correlations_to_crossover),
    # No distinct UI page by name yet -> keep canonical name, canonical payload.
    Adapter("funding_awards", "FundingAwards", STREAM_ID_FIELD["funding_awards"], None),
    Adapter("transactions", "Transactions", STREAM_ID_FIELD["transactions"], None),
    Adapter("observations", "Observations", STREAM_ID_FIELD["observations"], None),
]


# ── store helpers ───────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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

    Returns::

        {
          "db": "<db_path>",
          "collections": {"UnifiedSources": 4, "GraphNodes": 12, ...},
          "skipped": {"GraphNodes": 0, ...},   # rows missing their canonical id
          "total": 16,
        }

    Missing streams (and graph_summary.json) are silently skipped; ``total == 0``
    signals "nothing to ingest" to the caller.
    """
    agg = Path(aggregate_dir)
    db = Path(db_path)
    db.parent.mkdir(parents=True, exist_ok=True)

    ts = _now()
    collections: Dict[str, int] = {}
    skipped: Dict[str, int] = {}

    ctx = {"entity_module": _entity_module_map(agg)}

    conn = sqlite3.connect(db)
    try:
        conn.execute(_SCHEMA)
        for adapter in COLLECTION_ADAPTERS:
            fpath = agg / f"{adapter.stream}.jsonl"
            if not fpath.exists():
                continue
            upserted = 0
            missing = 0
            for row in _read_jsonl(fpath):
                entity_id = row.get(adapter.id_field)
                if not entity_id:
                    missing += 1
                    continue
                payload = dict(row)
                if adapter.project is not None:
                    payload.update(adapter.project(row, ctx))
                _upsert(conn, adapter.collection, str(entity_id), payload, ts)
                upserted += 1
            collections[adapter.collection] = upserted
            if missing:
                skipped[adapter.collection] = missing

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
