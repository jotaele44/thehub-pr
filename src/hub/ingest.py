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

Every stage (canonical streams, the CrossoverLinks projection, the per-domain UI
aliases) reduces to the same shape: a collection name plus ``(id, payload)``
pairs to upsert. Phase 3 pulls that shape out into one shared skeleton
(``_ingest_pairs``) so each stage is just a producer of pairs feeding it.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

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


# ── Phase 3: best-effort per-domain page collections ──────────────────────────
# The per-producer PAGES read rich per-domain collections. The canonical aggregate
# only carries id / name / entity_type / confidence / location / _producers, so this
# is a BEST-EFFORT projection: real entity lists + coordinates, with the rich fields
# the canonical lacks (municipality name, amounts, dates, operator, …) left null.
# GraphNodes/GraphEdges/UnifiedSources are NOT this function's job — the generic
# _UI_PROJECTIONS pass below already covers every producer's entities/relationships.
# Collections with no canonical source (witness/risk/anomaly records and the
# governance ledgers) are intentionally NOT populated here. AirspaceEvents maps
# skywatcher, but that producer currently exports a synthetic-only package, so the
# collection stays empty until skywatcher ships a real FR24 capture.
_LEDGER_CAP = 500

# (producer program_id, canonical entity_type) -> per-domain collection.
_PRODUCER_LEDGER: Dict[Tuple[str, str], str] = {
    ("aguayluz-pr", "utility_asset"): "InfrastructureAssets",
    ("ovnis-pr", "uap_case"): "UnifiedCases",
    ("moneysweep-pr", "recipient"): "Vendors",
    ("moneysweep-pr", "contract"): "Contracts",  # sparse (a few canonical contract entities); rich contract fields pending
    ("skywatcher-pr", "airspace_observation"): "AirspaceEvents",
}
# UnifiedCases also back the Ovnis page's PatternObservations view.
_LEDGER_ALIAS: Dict[str, str] = {"UnifiedCases": "PatternObservations"}


def _ledger_row(e: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """One canonical entity -> a per-domain page row (best-effort, generous aliases)."""
    eid = str(e["entity_id"])
    loc = e.get("location") or {}
    name = e.get("name")
    etype = e.get("entity_type")
    payload: Dict[str, Any] = {
        "id": eid, "entity_id": eid,
        # id aliases the various page components key on:
        "asset_id": eid, "vendor_id": eid, "event_id": eid,
        "case_id": eid, "pattern_id": eid, "contract_id": eid,
        "name": name, "title": name, "label": name or eid,
        "normalized_name": e.get("normalized_name"), "summary": e.get("normalized_name"),
        # type aliases (source-of-truth is entity_type):
        "entity_type": etype, "asset_type": etype, "event_type": etype,
        # band the raw 0–1 confidence into the same Low/Medium/High vocabulary the
        # generic UI projections use (_conf01_band), so a row reads consistently
        # across collections; keep the raw score too.
        "confidence": _conf01_band(e.get("confidence")),
        "confidence_score": e.get("confidence"),
        "latitude": loc.get("lat"), "longitude": loc.get("lon"),
        "source_id": e.get("source_id"), "_producers": e.get("_producers"),
        # rich fields absent from the canonical aggregate (pending richer producer exports):
        "municipality": None, "region": None, "status": None, "sensitivity": None,
        "award_amount": None, "award_date": None, "event_date": None,
        "operator": None, "owner_agency": None,
    }
    return eid, payload


def _ledger_collection(e: Dict[str, Any]) -> Optional[str]:
    """The ledger collection for an entity, checking every contributing producer.

    ``_producers`` is a sorted set (aggregate.py), not an owner-ordered list, so a
    multi-producer row (e.g. a recipient both centinelas-pr and moneysweep-pr
    contributed) can't just check index 0 — that misses the mapping if the
    alphabetically-first producer isn't the one ``_PRODUCER_LEDGER`` maps.
    """
    etype = str(e.get("entity_type") or "")
    for p in e.get("_producers") or []:
        collection = _PRODUCER_LEDGER.get((str(p), etype))
        if collection:
            return collection
    return None


def project_producer_collections(aggregate_dir: str | Path) -> Dict[str, List[Tuple[str, Dict[str, Any]]]]:
    """Best-effort projection of canonical entities into the per-producer page collections.

    Maps ``(producer, entity_type) -> collection`` for any producer on the row, keeps
    real (non-synthetic) rows with a canonical id, prefers geocoded + high-confidence,
    caps ``_LEDGER_CAP`` per collection. Returns ``{collection: [(entity_id, payload), ...]}``.
    """
    agg = Path(aggregate_dir)
    ent_path = agg / "entities.jsonl"
    if not ent_path.exists():
        return {}

    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for e in _read_jsonl(ent_path):
        if e.get("synthetic") or not e.get("entity_id"):
            continue
        collection = _ledger_collection(e)
        if not collection:
            continue
        buckets.setdefault(collection, []).append(e)

    out: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
    for collection, rows in buckets.items():
        rows.sort(
            key=lambda e: (((e.get("location") or {}).get("lat") is not None), e.get("confidence") or 0),
            reverse=True,
        )
        projected = [_ledger_row(e) for e in rows[:_LEDGER_CAP]]
        out[collection] = projected
        alias = _LEDGER_ALIAS.get(collection)
        if alias:
            out[alias] = projected

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


# ── Phase 2: frontend-facing per-domain projections ──────────────────────────
# Alongside the canonical collections above, several UI pages read per-domain
# collections whose field names differ from the canonical streams (Sources.jsx ->
# UnifiedSources, Spiderweb.jsx -> GraphNodes/GraphEdges, GovernanceAlertsPanel ->
# GovernanceAlerts). We project each stream into its UI collection, keeping the
# full canonical payload (incl. _producers) and *adding* the UI field aliases, so
# those pages render live aggregate data without losing provenance. Streams keep
# their canonical collection too (the aggregate graph stays intact for consumers).

# Canonical alert status -> the UI's GovernanceAlerts review_status. The panel
# treats only {"Open","Acknowledged"} as open, so live alerts must be translated
# or they render as closed/hidden. Unknown -> "Open" (surface it for review).
_ALERT_REVIEW_STATUS = {
    "draft": "Open", "active": "Open", "validated": "Acknowledged",
    "closed": "Closed", "rejected": "Rejected",
}


def _conf01_band(value: Any) -> Optional[str]:
    """Bucket a 0..1 confidence into the UI's Low/Medium/High select values."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return "Low" if v < 0.5 else "Medium" if v < 0.8 else "High"


def _loc(row: Dict[str, Any], key: str) -> Any:
    loc = row.get("location")
    return loc.get(key) if isinstance(loc, dict) else None


def _nonnull(fields: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in fields.items() if v is not None}


def _alias_source(row: Dict[str, Any]) -> Dict[str, Any]:
    return _nonnull({
        "source_id": row.get("source_id"),
        "title": row.get("source_name"),
        "source_type": row.get("source_type"),
        "url": row.get("source_url") or row.get("source_ref"),
        "program_id": _first_producer(row) or None,
    })


def _alias_node(row: Dict[str, Any]) -> Dict[str, Any]:
    return _nonnull({
        "node_id": row.get("entity_id"),
        "label": row.get("name"),
        "node_type": row.get("entity_type"),
        "municipality": _loc(row, "municipality"),
        "latitude": _loc(row, "lat"),
        "longitude": _loc(row, "lon"),
        "confidence": _conf01_band(row.get("confidence")),
        "program_id": _first_producer(row) or None,
    })


def _alias_edge(row: Dict[str, Any]) -> Dict[str, Any]:
    return _nonnull({
        "edge_id": row.get("relationship_id"),
        "source_node_id": row.get("source_entity_id"),
        "target_node_id": row.get("target_entity_id"),
        "relationship_type": row.get("relationship_type"),
        "confidence": _conf01_band(row.get("confidence")),
    })


def _alias_alert(row: Dict[str, Any]) -> Dict[str, Any]:
    status = row.get("status")
    review = _ALERT_REVIEW_STATUS.get(status, "Open") if isinstance(status, str) else "Open"
    attrs = row.get("attributes")
    attrs = attrs if isinstance(attrs, dict) else {}
    return _nonnull({
        "module": row.get("module"),
        "entity_name": row.get("module"),
        "severity": row.get("severity"),
        "review_status": review,
        "occurred_at": row.get("observed_at"),
        "record_id": row.get("entity_id"),
        "summary": attrs.get("summary") or row.get("alert_type"),
    })


# (stream, id field, UI collection, alias projector) — canonical row + UI aliases.
_UI_PROJECTIONS: List[Tuple[str, str, str, Callable[[Dict[str, Any]], Dict[str, Any]]]] = [
    ("sources", "source_id", "UnifiedSources", _alias_source),
    ("entities", "entity_id", "GraphNodes", _alias_node),
    ("relationships", "relationship_id", "GraphEdges", _alias_edge),
    ("alerts", "alert_id", "GovernanceAlerts", _alias_alert),
]


def _project_ui(agg: Path, stream: str, id_field: str,
                alias: Callable[[Dict[str, Any]], Dict[str, Any]]) -> List[Tuple[str, Dict[str, Any]]]:
    path = agg / f"{stream}.jsonl"
    if not path.exists():
        return []
    out: List[Tuple[str, Dict[str, Any]]] = []
    for row in _read_jsonl(path):
        eid = row.get(id_field)
        if not eid:
            continue
        out.append((str(eid), {**row, **alias(row)}))
    return out


# ── Phase 3: shared producer skeleton ─────────────────────────────────────────
# Every stage above (canonical streams, CrossoverLinks, per-domain UI aliases)
# ultimately produces the same shape: a collection name plus a list of
# (id, payload) pairs to upsert. _ingest_pairs is the one place that shape gets
# written to the store and tallied, so each stage is just a producer of pairs.


def _canonical_pairs(agg: Path, stream: str, id_field: str,
                      ) -> Optional[Tuple[List[Tuple[str, Dict[str, Any]]], int]]:
    """(id, row) pairs for a canonical stream, plus its count of id-less rows.

    Returns ``None`` if the stream file is absent (caller skips it entirely,
    as opposed to a present-but-empty file — see ``_ingest_pairs(..., always=True)``).
    """
    path = agg / f"{stream}.jsonl"
    if not path.exists():
        return None
    pairs: List[Tuple[str, Dict[str, Any]]] = []
    missing = 0
    for row in _read_jsonl(path):
        eid = row.get(id_field)
        if not eid:
            missing += 1
            continue
        pairs.append((str(eid), row))
    return pairs, missing


def _ingest_pairs(conn: sqlite3.Connection, collection: str,
                   pairs: List[Tuple[str, Dict[str, Any]]], ts: str,
                   collections: Dict[str, int], missing: int = 0,
                   skipped: Optional[Dict[str, int]] = None, always: bool = False) -> None:
    """Upsert ``(id, payload)`` pairs into ``collection`` and tally the counts.

    ``always`` records the collection's count even when ``pairs`` is empty
    (used for canonical streams, where a present-but-empty file is still
    reported); projections instead only tally when they produced rows.
    """
    n = 0
    for eid, payload in pairs:
        _upsert(conn, collection, eid, payload, ts)
        n += 1
    if n or always:
        collections[collection] = n
    if missing and skipped is not None:
        skipped[collection] = missing


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
            result = _canonical_pairs(agg, stream, _ID_FIELD[stream])
            if result is None:
                continue
            pairs, missing = result
            _ingest_pairs(conn, collection, pairs, ts, collections, missing, skipped, always=True)

        summary_path = agg / "graph_summary.json"
        if summary_path.exists():
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            _ingest_pairs(conn, _SUMMARY_COLLECTION, [(_SUMMARY_ID, payload)], ts, collections, always=True)

        # Phase 3: project correlations into the workspace's explicit CrossoverLinks.
        _ingest_pairs(conn, _CROSSOVER_COLLECTION, project_crossover_links(agg), ts, collections)

        # Phase 3: project each stream into its per-domain UI collection.
        for stream, id_field, collection, alias in _UI_PROJECTIONS:
            _ingest_pairs(conn, collection, _project_ui(agg, stream, id_field, alias), ts, collections)

        # Phase 3: best-effort per-domain page collections (Vendors/InfrastructureAssets/…)
        # not covered by the generic UI projections above.
        for collection, rows in project_producer_collections(agg).items():
            _ingest_pairs(conn, collection, rows, ts, collections)

        conn.commit()
    finally:
        conn.close()

    return {
        "db": str(db),
        "collections": collections,
        "skipped": skipped,
        "total": sum(collections.values()),
    }
