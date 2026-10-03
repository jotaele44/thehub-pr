"""Event timeline API: ``GET /api/timeline``.

Read-only. Orders the OVNIS case observations the Hub store already holds
(``hub.event_timeline``). Findings attach through the OVNIS research-ledger
finding rows that name a case (``hub.research_composition.finding_links``). For
the events on the requested page it adds the cited source's name and URL, and
falls back to the case entity for the case id and narrative when an older export
carried them only there. No other producer database is read and nothing is
inferred.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from hub import epistemic as ep
from hub import research_composition as rc
from hub.event_timeline import DEFAULT_LIMIT, MAX_LIMIT, OBSERVATION_TYPE, build_timeline, parse_cursor
from hub.ingest import STREAM_TO_COLLECTION
from server.backend.entity_api import _query
from server.backend.evidence_api import _SOURCES_COLLECTION, _load

router = APIRouter(prefix="/api/timeline", tags=["timeline"])

_OBSERVATIONS = STREAM_TO_COLLECTION["observations"]
_ENTITIES = STREAM_TO_COLLECTION["entities"]


def _case_observations() -> List[Dict[str, Any]]:
    return [row for _, row in _query(
        "SELECT entity_type, data FROM entities WHERE entity_type = ? "
        "AND json_extract(data, '$.observation_type') = ?",
        (_OBSERVATIONS, OBSERVATION_TYPE),
    )]


def _finding_links(observations: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    case_entities = {str(ep.as_mapping(row.get("attributes")).get("case_id")): str(row.get("entity_id"))
                     for row in observations if ep.as_mapping(row.get("attributes")).get("case_id")}
    findings = [row for _, row in _query(
        "SELECT entity_type, data FROM entities WHERE entity_type = ? AND json_extract(data, '$.entity_type') = ?",
        (_ENTITIES, rc.KINDS["findings"][0]),
    )]
    return rc.finding_links(findings, case_entities)


def _enrich(events: List[Dict[str, Any]]) -> None:
    sources = _load(_SOURCES_COLLECTION, [str(e.get("source_id") or "") for e in events])
    entities = _load(_ENTITIES, [str(e.get("entity_id") or "") for e in events])
    for event in events:
        source = sources.get(str(event.get("source_id") or ""))
        event["source"] = (
            {"source_id": event["source_id"], "name": source.get("source_name"), "url": source.get("source_url"),
             "evidence_href": f"/evidence/{_SOURCES_COLLECTION}/{event['source_id']}"}
            if source else None
        )
        entity = entities.get(str(event.get("entity_id") or "")) or {}
        attrs = ep.as_mapping(entity.get("attributes"))
        if event["case_id"] is None:
            event["case_id"] = attrs.get("case_id") or ep.as_mapping(entity.get("external_ids")).get("ovnis_case_id")
        if event["narrative"] is None:
            event["narrative"] = attrs.get("description")


@router.get("")
def timeline(
    sort: str = Query("oldest"),
    category: Optional[List[str]] = Query(None),
    findings_only: bool = Query(False),
    include_synthetic: bool = Query(False),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    cursor: Optional[str] = Query(None, max_length=12),
) -> Dict[str, Any]:
    observations = _case_observations()
    try:
        result = build_timeline(
            observations, sort=sort, categories=tuple(category or ()), findings_only=findings_only,
            include_synthetic=include_synthetic, finding_links=_finding_links(observations), limit=limit,
            offset=parse_cursor(cursor),
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    _enrich(result["events"])
    return result
