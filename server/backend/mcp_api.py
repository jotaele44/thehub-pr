"""Hosted MCP API — mounts the federation Router as FastAPI routes.

In-process only: this exposes the existing runtime library over HTTP for
operator use. Adapter execution, policy enforcement, and provenance stamping
all happen in `hub.mcp_runtime`; this module is a thin transport that maps
runtime exceptions to HTTP status codes and logs provenance as structured
JSON lines.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from hub.mcp_runtime import (
    MCPRequest,
    PolicyViolation,
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


class RouteRequest(BaseModel):
    project: str
    capability: str
    action: str
    params: Dict[str, Any] = {}
    is_write: bool = False


def _log_provenance(record: Dict[str, Any]) -> None:
    logger.info(json.dumps(record, sort_keys=True, default=str))


def create_default_hub_router() -> Router:
    """Wire the registry + core and domain adapters with a JSON provenance log.

    Adapters use their production defaults (EnvHttpClient / env credentials);
    unresolvable credentials fail closed at request time, so registration is
    always safe even when no keys are configured.
    """
    registry = RuntimeRegistry()
    router = Router(registry, provenance_sink=_log_provenance)
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
    """Build an APIRouter over an already-wired hub Router."""
    api = APIRouter()

    @api.get("/healthz")
    def healthz() -> Dict[str, str]:
        return {"status": "ok"}

    @api.get("/readyz")
    def readyz() -> Dict[str, str]:
        ready = bool(router.registry.capabilities) and bool(
            router.registered_capabilities()
        )
        if not ready:
            raise HTTPException(status_code=503, detail="not ready")
        return {"status": "ready"}

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
        return {
            "status": result.status,
            "data": result.data,
            "provenance": result.provenance,
        }

    return api
