"""Hosted MCP API and read-only federal-record review routes."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from hub.mcp_runtime import (
    InMemoryMetrics,
    LoggingMetricsSink,
    MCPRequest,
    MultiMetricsSink,
    PolicyViolation,
    ResponseCache,
    Router,
    RuntimeRegistry,
)
from hub.mcp_runtime.adapters import (
    DocumentsAdapter,
    GeospatialAdapter,
    GithubBridgeAdapter,
    ProvenanceAdapter,
)
from hub.mcp_runtime.adapters.domain import DOMAIN_ADAPTERS

logger = logging.getLogger("hub.mcp")
DB_PATH = Path(__file__).parents[2] / "data" / "hub.db"

FEDERAL_COLLECTIONS = {
    "documents": "FederalDocuments",
    "releases": "FederalDocumentReleases",
    "findings": "DocumentFindings",
    "candidates": "CaseActivityCandidates",
    "assessments": "CaseActivityAssessments",
}


class RouteRequest(BaseModel):
    project: str
    capability: str
    action: str
    params: Dict[str, Any] = {}
    is_write: bool = False


def _log_provenance(record: Dict[str, Any]) -> None:
    logger.info(json.dumps(record, sort_keys=True, default=str))


def _federal_rows(
    collection: str,
    *,
    case_id: Optional[str] = None,
    municipality: Optional[str] = None,
    facility: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT data FROM entities WHERE entity_type=? ORDER BY updated_at DESC LIMIT ?",
        (collection, min(max(limit, 1), 5000)),
    ).fetchall()
    conn.close()
    output: list[dict[str, Any]] = []
    for (raw,) in rows:
        row = json.loads(raw)
        serialized = json.dumps(row, sort_keys=True).lower()
        if case_id and case_id.lower() not in serialized:
            continue
        if municipality and municipality.lower() not in serialized:
            continue
        if facility and facility.lower() not in serialized:
            continue
        row_date = str(
            row.get("document_date_start")
            or row.get("released_at")
            or row.get("created_at")
            or ""
        )[:10]
        if date_from and row_date and row_date < date_from:
            continue
        if date_to and row_date and row_date > date_to:
            continue
        output.append(row)
    return output


def ensure_federal_indexes(db_path: Path = DB_PATH) -> None:
    """Add query indexes without changing existing entity rows."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS entities ("
        "entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, data TEXT NOT NULL, "
        "updated_at TEXT NOT NULL, PRIMARY KEY (entity_type, entity_id))"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_entities_type_updated "
        "ON entities(entity_type, updated_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_entities_type_id "
        "ON entities(entity_type, entity_id)"
    )
    conn.commit()
    conn.close()


def create_default_hub_router() -> Router:
    registry = RuntimeRegistry()
    router = Router(
        registry,
        provenance_sink=_log_provenance,
        metrics_sink=MultiMetricsSink([InMemoryMetrics(), LoggingMetricsSink()]),
        cache=ResponseCache(ttl_seconds=30.0),
    )
    for adapter in (
        ProvenanceAdapter(),
        GeospatialAdapter(),
        DocumentsAdapter(),
        GithubBridgeAdapter(),
    ):
        router.register_adapter(adapter)
    for adapter_cls in DOMAIN_ADAPTERS:
        router.register_adapter(adapter_cls())
    return router


def build_mcp_api(router: Router) -> APIRouter:
    api = APIRouter()
    ensure_federal_indexes()

    @api.get("/healthz")
    def healthz() -> Dict[str, str]:
        return {"status": "ok"}

    @api.get("/readyz")
    def readyz() -> Dict[str, str]:
        ready = bool(router.registry.capabilities) and bool(router.registered_capabilities())
        if not ready:
            raise HTTPException(status_code=503, detail="not ready")
        return {"status": "ready"}

    @api.get("/mcp/metrics")
    def metrics() -> Dict[str, Any]:
        sink = router.metrics_sink
        candidates = sink.sinks if isinstance(sink, MultiMetricsSink) else [sink]
        for candidate in candidates:
            if isinstance(candidate, InMemoryMetrics):
                return candidate.aggregates()
        return {"count": 0, "detail": "no in-memory metrics collector"}

    @api.get("/mcp/capabilities")
    def capabilities() -> Dict[str, Any]:
        caps = {
            name: {
                "class": cap.capability_class,
                "status": cap.status,
                "version_pin": cap.version_pin,
                "required_by": cap.required_by,
            }
            for name, cap in router.registry.capabilities.items()
        }
        projects = {
            project: {
                "inherits": manifest.inherits,
                "capabilities": manifest.capabilities,
                "write_default": manifest.write_default,
            }
            for project, manifest in router.registry.manifests.items()
        }
        return {"capabilities": caps, "projects": projects}

    @api.post("/mcp/route")
    def route(body: RouteRequest) -> Dict[str, Any]:
        request = MCPRequest(
            project=body.project,
            capability=body.capability,
            action=body.action,
            params=dict(body.params),
            is_write=body.is_write,
        )
        try:
            result = router.route(request)
        except PolicyViolation as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc))
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"status": result.status, "data": result.data, "provenance": result.provenance}

    @api.get("/api/federal-records/{surface}")
    def federal_records(
        surface: str,
        case_id: Optional[str] = Query(None),
        municipality: Optional[str] = Query(None),
        facility: Optional[str] = Query(None),
        date_from: Optional[str] = Query(None),
        date_to: Optional[str] = Query(None),
        limit: int = Query(500, ge=1, le=5000),
    ) -> Dict[str, Any]:
        collection = FEDERAL_COLLECTIONS.get(surface)
        if collection is None:
            raise HTTPException(status_code=404, detail=f"unknown federal-record surface: {surface}")
        rows = _federal_rows(
            collection,
            case_id=case_id,
            municipality=municipality,
            facility=facility,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
        return {"surface": surface, "count": len(rows), "items": rows, "read_only": True}

    @api.get("/api/cases/{case_id}/fedmil-context")
    def case_context(case_id: str) -> Dict[str, Any]:
        candidates = _federal_rows("CaseActivityCandidates", case_id=case_id, limit=5000)
        assessments = _federal_rows("CaseActivityAssessments", case_id=case_id, limit=5000)
        return {
            "case_id": case_id,
            "candidates": candidates,
            "assessments": assessments,
            "contradictions": [row for row in assessments if row.get("classification") == "CONTRADICTORY"],
            "data_gaps": [row for row in assessments if row.get("classification") == "DATA_GAP"],
            "read_only": True,
        }

    return api
