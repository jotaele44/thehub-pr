"""Federation Constellation API: ``GET /api/constellation``.

Read-only. Joins ``registry/constellation.v1.json`` (the stage tour and the code
components of each app) with what the Hub store holds: the exported totals in
``FederationSummary/graph_summary``, the rows stored per producer and stream,
their ``lineage``, a few sample rows, and the correlation candidates with both
endpoints resolved to the producer stream they came from. ``hub.constellation``
assembles the two lenses; no producer is contacted and nothing is inferred.
"""

from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from fastapi import APIRouter

from hub.constellation import SAMPLE_LIMIT, SPEC_FILE, STREAMS, CorrelationRow, StoreSnapshot, build_constellation
from hub.constellation import load_spec, sample_view
from hub.ingest import _SUMMARY_COLLECTION, _SUMMARY_ID, STREAM_TO_COLLECTION
from hub.registry import load_registry
from server.backend.evidence_api import _core

router = APIRouter(prefix="/api/constellation", tags=["constellation"])

_CANONICAL = {STREAM_TO_COLLECTION[s]: s for s in STREAMS}
_CORRELATIONS = STREAM_TO_COLLECTION["correlations"]
_ID_CHUNK = 500


def _rows(sql: str, params: Sequence[Any] = ()) -> List[Tuple[Any, ...]]:
    with closing(_core()._conn()) as conn:
        return [tuple(r) for r in conn.execute(sql, tuple(params)).fetchall()]


def _in(values: Sequence[str]) -> str:
    return ",".join("?" for _ in values)


def _summary() -> Optional[Dict[str, Any]]:
    rows = _rows("SELECT data FROM entities WHERE entity_type = ? AND entity_id = ?", (_SUMMARY_COLLECTION, _SUMMARY_ID))
    return json.loads(rows[0][0]) if rows else None


def _stored_and_lineage(snapshot: StoreSnapshot) -> None:
    collections = list(_CANONICAL)
    lineage: Dict[Tuple[str, str], Dict[Tuple[str, str], Dict[str, Any]]] = {}
    for collection, producer, script, phase, inputs, count in _rows(
        "SELECT e.entity_type, p.value, json_extract(e.data, '$.lineage.producer_script'), "
        "json_extract(e.data, '$.lineage.producer_phase'), json_extract(e.data, '$.lineage.source_inputs'), COUNT(*) "
        f"FROM entities e, json_each(e.data, '$._producers') p WHERE e.entity_type IN ({_in(collections)}) "
        "GROUP BY 1, 2, 3, 4, 5",
        collections,
    ):
        key = (str(producer), _CANONICAL[collection])
        snapshot.stored[key] = snapshot.stored.get(key, 0) + int(count)
        entry = lineage.setdefault(key, {}).setdefault(
            (script or "", phase or ""), {"script": script, "phase": phase, "count": 0, "inputs": {}})
        entry["count"] += int(count)
        for name in json.loads(inputs) if inputs else []:
            entry["inputs"][str(name)] = entry["inputs"].get(str(name), 0) + int(count)
    for key, entries in lineage.items():
        snapshot.lineage[key] = [{
            **{k: v for k, v in e.items() if k != "inputs"},
            "inputs": [name for name, _ in sorted(e["inputs"].items(), key=lambda kv: (-kv[1], kv[0]))[:3]],
        } for e in sorted(entries.values(), key=lambda e: (-e["count"], e["script"] or ""))]


def _samples(snapshot: StoreSnapshot) -> None:
    for producer, stream in sorted(snapshot.stored):
        collection = STREAM_TO_COLLECTION[stream]
        snapshot.samples[(producer, stream)] = [sample_view(collection, json.loads(data), record_id) for record_id, data in _rows(
            "SELECT e.entity_id, e.data FROM entities e WHERE e.entity_type = ? AND EXISTS "
            "(SELECT 1 FROM json_each(e.data, '$._producers') p WHERE p.value = ?) ORDER BY e.entity_id LIMIT ?",
            (collection, producer, SAMPLE_LIMIT),
        )]


def _endpoints(ids: Sequence[str]) -> Dict[str, Tuple[str, str]]:
    """Canonical row id -> (first producer, stream), for the rows the store holds."""
    found: Dict[str, Tuple[str, str]] = {}
    collections = list(_CANONICAL)
    unique = sorted(set(ids))
    for i in range(0, len(unique), _ID_CHUNK):
        chunk = unique[i:i + _ID_CHUNK]
        for collection, record_id, producers in _rows(
            f"SELECT entity_type, entity_id, json_extract(data, '$._producers') FROM entities "
            f"WHERE entity_type IN ({_in(collections)}) AND entity_id IN ({_in(chunk)})",
            (*collections, *chunk),
        ):
            names = sorted(json.loads(producers)) if producers else []
            if names and record_id not in found:
                found[record_id] = (names[0], _CANONICAL[collection])
    return found


def _correlations(snapshot: StoreSnapshot) -> None:
    rows = _rows(
        "SELECT entity_id, json_extract(data, '$.relationship_type'), json_extract(data, '$.match_basis'), "
        "json_extract(data, '$.synthetic'), json_extract(data, '$.explanation'), "
        "json_extract(data, '$.source_entity_id'), json_extract(data, '$.target_entity_id') "
        "FROM entities WHERE entity_type = ?",
        (_CORRELATIONS,),
    )
    ends = _endpoints([str(r[i]) for r in rows for i in (5, 6) if r[i]])
    snapshot.correlations = [CorrelationRow(
        relationship_id=str(rid), relationship_type=str(rtype or ""), match_basis=str(basis or ""),
        synthetic=bool(synthetic), explanation=str(explanation or ""),
        source=ends.get(str(src)), target=ends.get(str(dst)),
    ) for rid, rtype, basis, synthetic, explanation, src, dst in rows]


def store_snapshot() -> StoreSnapshot:
    snapshot = StoreSnapshot(summary=_summary())
    snapshot.collections = {str(c): int(n) for c, n in _rows("SELECT entity_type, COUNT(*) FROM entities GROUP BY 1")}
    _stored_and_lineage(snapshot)
    _samples(snapshot)
    _correlations(snapshot)
    return snapshot


def _registry_status(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    return {p.program_id: p.status for p in load_registry(path).producers}


@router.get("")
def constellation() -> Dict[str, Any]:
    registry_path = Path(_core().REGISTRY_PATH)
    spec = load_spec(registry_path.parent / SPEC_FILE)
    return build_constellation(spec, store_snapshot(), _registry_status(registry_path))
