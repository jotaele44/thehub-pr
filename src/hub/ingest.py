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
from typing import Any, Dict, List, Tuple

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

# ── Phase 2: frontend-facing CrossoverLinks projection ────────────────────────
# The Crossover Workspace (server/frontend/src/lib/crossover.js) is explicit-only:
# it renders the "CrossoverLinks" collection. Phase 1 above loads the canonical
# `correlations` stream verbatim into "Correlations"; this projects those rows
# into the workspace's display shape and curates the volume so the frontend's
# bounded page (useEntityData caps at _CROSSOVER_CAP) shows the strongest links.
_CROSSOVER_COLLECTION = "CrossoverLinks"
_CROSSOVER_CAP = 500

# producer program_id -> crossover-config.js CROSSOVER_MODULES string.
_PRODUCER_MODULE: Dict[str, str] = {
    "aguayluz-pr": "AguaYLuz-PR", "ovnis-pr": "Ovnis-PR", "moneysweep-pr": "MoneySweep-PR",
    "spiderweb-pr": "Spiderweb-PR", "skywatcher-pr": "Skywatcher-PR", "centinelas-pr": "Centinelas-PR",
}
# correlate relationship_type -> crossover-config.js correlation_type.
_CROSSOVER_TYPE: Dict[str, str] = {
    "spatial_proximity": "Geography", "spatial_correlation": "Geography",
    "temporal_proximity": "Temporal", "temporal_correlation": "Temporal",
    "entity_correlation": "Entity",
}
# aguayluz is the dense side we collapse AGAINST; spatial links dedupe to the
# nearest cross-producer match per one of these (minority) entities, otherwise
# municipality-centroid geocoding explodes them (one case ~ thousands of assets).
_MINORITY_PRODUCERS = {"ovnis-pr", "spiderweb-pr", "skywatcher-pr", "centinelas-pr", "moneysweep-pr"}


def _first_producer(entity: Dict[str, Any]) -> str:
    ps = entity.get("_producers") or []
    return str(ps[0]) if ps else ""


def _crossover_band(score: float) -> str:
    return "High" if score >= 70 else "Medium" if score >= 40 else "Low"


def project_crossover_links(aggregate_dir: str | Path) -> List[Tuple[str, Dict[str, Any]]]:
    """Reshape ``correlations.jsonl`` into the explicit CrossoverLinks the workspace reads.

    Curation: keep every entity-name correlation; collapse spatial/temporal links
    to the single nearest cross-producer match per minority-producer entity; cap
    the total to ``_CROSSOVER_CAP`` by descending confidence. Returns
    ``(crossover_id, payload)`` pairs; empty if there is no correlations stream.
    """
    agg = Path(aggregate_dir)
    corr_path = agg / "correlations.jsonl"
    if not corr_path.exists():
        return []
    ent_path = agg / "entities.jsonl"
    ents = {e["entity_id"]: e for e in _read_jsonl(ent_path)} if ent_path.exists() else {}

    name_links: List[Dict[str, Any]] = []
    spatial_best: Dict[str, Dict[str, Any]] = {}
    for r in _read_jsonl(corr_path):
        if r.get("relationship_type") == "entity_correlation":
            name_links.append(r)
            continue
        a, b = r.get("source_entity_id"), r.get("target_entity_id")
        key = a if _first_producer(ents.get(a, {})) in _MINORITY_PRODUCERS else b
        conf = r.get("confidence") or 0
        if key is not None and (key not in spatial_best or conf > (spatial_best[key].get("confidence") or 0)):
            spatial_best[key] = r

    curated = name_links + list(spatial_best.values())
    curated.sort(key=lambda r: r.get("confidence") or 0, reverse=True)

    out: List[Tuple[str, Dict[str, Any]]] = []
    for r in curated[:_CROSSOVER_CAP]:
        a = ents.get(r.get("source_entity_id"), {})
        b = ents.get(r.get("target_entity_id"), {})
        score = round((r.get("confidence") or 0) * 100)
        sm = _PRODUCER_MODULE.get(_first_producer(a), "Hub")
        tm = _PRODUCER_MODULE.get(_first_producer(b), "Hub")
        cid = r.get("relationship_id") or f"xover_{r.get('source_entity_id')}_{r.get('target_entity_id')}"
        basis = r.get("match_basis")
        out.append((cid, {
            "crossover_id": cid,
            "source_module": sm, "target_module": tm,
            "source_record_id": r.get("source_entity_id"),
            "target_record_id": r.get("target_entity_id"),
            "source_label": a.get("name") or r.get("source_entity_id"),
            "target_label": b.get("name") or r.get("target_entity_id"),
            "related_modules": sorted({sm, tm}),
            "correlation_type": _CROSSOVER_TYPE.get(r.get("relationship_type") or "", "Other"),
            "status": "Candidate",
            "confidence_score": score,
            "confidence_band": _crossover_band(score),
            "rationale": r.get("explanation", ""),
            "matching_criteria": [basis] if basis else [],
            "source_ids": [],
            "evidence_tier": None,
            "created_from": "hub correlate",
        }))
    return out


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

        # Phase 2: project correlations into the workspace's explicit CrossoverLinks.
        xlinks = project_crossover_links(agg)
        for cid, payload in xlinks:
            _upsert(conn, _CROSSOVER_COLLECTION, cid, payload, ts)
        if xlinks:
            collections[_CROSSOVER_COLLECTION] = len(xlinks)

        conn.commit()
    finally:
        conn.close()

    return {
        "db": str(db),
        "collections": collections,
        "skipped": skipped,
        "total": sum(collections.values()),
    }
