"""Authenticated, loopback-only read surface for Federation Manager v0.3."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from ipaddress import ip_address

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from server.backend.federation_manager import SessionManager, read_only_inventory

router = APIRouter(prefix="/api/federation-manager", tags=["federation-manager"])

ALLOWED_ORIGINS = {
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
}
_bootstrap_nonce = os.environ.get("PRII_MANAGER_BOOTSTRAP_NONCE", "")
sessions = SessionManager(_bootstrap_nonce, ALLOWED_ORIGINS, ttl_seconds=300)


class SessionRequest(BaseModel):
    nonce: str = Field(min_length=32)
    origin: str


def _require_loopback(request: Request) -> None:
    host = request.client.host if request.client else ""
    try:
        if not ip_address(host).is_loopback:
            raise HTTPException(status_code=403, detail="manager API is loopback only")
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="manager API is loopback only") from exc


def _origin(request: Request) -> str:
    origin = request.headers.get("origin", "")
    if origin not in ALLOWED_ORIGINS:
        raise HTTPException(status_code=403, detail="origin is not allowed")
    return origin


def _authorize(request: Request, authorization: str | None) -> None:
    _require_loopback(request)
    origin = _origin(request)
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="manager session required")
    if not sessions.validate(authorization[7:], origin):
        raise HTTPException(status_code=401, detail="manager session invalid or expired")


@router.post("/session")
def create_session(body: SessionRequest, request: Request):
    _require_loopback(request)
    if not _bootstrap_nonce:
        raise HTTPException(status_code=503, detail="native bootstrap is not configured")
    if body.origin != _origin(request):
        raise HTTPException(status_code=403, detail="origin mismatch")
    try:
        token, expires = sessions.exchange(body.nonce, body.origin)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {
        "token": token,
        "expiresAt": datetime.fromtimestamp(expires, timezone.utc).isoformat(),
    }


@router.get("/apps")
def list_apps(request: Request, authorization: str | None = Header(None)):
    _authorize(request, authorization)
    return read_only_inventory()


@router.get("/apps/{app_id}")
def get_app(app_id: str, request: Request, authorization: str | None = Header(None)):
    _authorize(request, authorization)
    for app in read_only_inventory():
        if app["appId"] == app_id:
            return app
    raise HTTPException(status_code=404, detail="unknown app")
