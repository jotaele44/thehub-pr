"""Research API: ``GET /api/research``, ``/api/research/records/{kind}`` and
``/api/research/case/{case_id}``.

Read-only. Serves the OVNIS research records the Hub store already holds
(``hub.research_composition``): an overview with topic cards, one kind's records
page by page, and a single case reconstructed from its own rows plus every
research record that names it. Nothing is inferred or matched here; a case pair
stays the CANDIDATE OVNIS exported until a curated adjudication decides it.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from fastapi import APIRouter, HTTPException, Query

from hub import epistemic as ep
from hub import research_composition as rc
from hub.event_timeline import parse_cursor
from hub.ingest import STREAM_TO_COLLECTION
from server.backend.entity_api import _query
from server.backend.evidence_api import _SOURCES_COLLECTION, _load

router = APIRouter(prefix="/api/research", tags=["research"])

_ENTITIES = STREAM_TO_COLLECTION["entities"]
_OBSERVATIONS = STREAM_TO_COLLECTION["observations"]


def _entities_of_types(types: tuple) -> List[Dict[str, Any]]:
    marks = ",".join("?" for _ in types)
    return [row for _, row in _query(
        f"SELECT entity_type, data FROM entities WHERE entity_type = ? "
        f"AND json_extract(data, '$.entity_type') IN ({marks}) ORDER BY entity_id",
        (_ENTITIES, *types),
    )]


def research_rows() -> List[Dict[str, Any]]:
    return _entities_of_types(rc.ENTITY_TYPES)


def _case_id(row: Mapping[str, Any]) -> str:
    return str(ep.as_mapping(row.get("attributes")).get("case_id")
               or ep.as_mapping(row.get("external_ids")).get("ovnis_case_id") or "")


def _cases_by_id(case_ids: Optional[set] = None) -> Dict[str, Dict[str, Any]]:
    cases = {_case_id(row): row for row in _entities_of_types((rc.CASE_TYPE,))}
    return {k: v for k, v in cases.items() if k and (case_ids is None or k in case_ids)}


def _observations_for(entity_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    if not entity_ids:
        return {}
    marks = ",".join("?" for _ in entity_ids)
    rows = _query(
        f"SELECT entity_type, data FROM entities WHERE entity_type = ? AND json_extract(data, '$.entity_id') IN ({marks}) "
        "AND json_extract(data, '$.observation_type') = ?",
        (_OBSERVATIONS, *entity_ids, rc.CASE_TYPE),
    )
    return {str(row.get("entity_id")): row for _, row in rows}


@router.get("")
def research_overview(include_synthetic: bool = Query(False)) -> Dict[str, Any]:
    rows = research_rows()
    case_sources = {key: str(row.get("source_id") or "") for key, row in _cases_by_id().items()}
    return rc.overview(rows, case_sources=case_sources, include_synthetic=include_synthetic)


@router.get("/records/{kind}")
def research_records(
    kind: str,
    status: Optional[str] = Query(None, max_length=32),
    origin: Optional[str] = Query(None, max_length=16),
    include_synthetic: bool = Query(False),
    limit: int = Query(rc.DEFAULT_LIMIT, ge=1, le=rc.MAX_LIMIT),
    cursor: Optional[str] = Query(None, max_length=12),
) -> Dict[str, Any]:
    try:
        return rc.records(kind, research_rows(), status=status, origin=origin, include_synthetic=include_synthetic,
                          limit=limit, offset=parse_cursor(cursor))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/case/{case_id}")
def research_case(case_id: str, include_synthetic: bool = Query(False)) -> Dict[str, Any]:
    rows = [row for row in research_rows() if case_id in rc.cases_named(row)]
    named = {case_id} | {c for row in rows for c in rc.cases_named(row)}
    cases = _cases_by_id(named)
    case = cases.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"OVNIS case {case_id!r} is not held by this Hub")
    observations = _observations_for([str(row.get("entity_id")) for row in cases.values()])
    others = {key: rc.case_summary(row, observations.get(str(row.get("entity_id"))))
              for key, row in cases.items() if key != case_id}
    source = _load(_SOURCES_COLLECTION, [str(case.get("source_id") or "")]).get(str(case.get("source_id") or ""))
    return rc.case_reconstruction(
        case, observation=observations.get(str(case.get("entity_id"))), source=source, research_rows=rows,
        other_cases=others, include_synthetic=include_synthetic,
    )
