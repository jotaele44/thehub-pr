"""Authenticated, loopback-only manager API.

Phase 1 (PR #94) exposed a read-only inventory behind three gates: loopback
only, an exact origin allow-list, and a short-lived opaque bearer token. This
module keeps that chain and adds the operations plane on top of it -- plan,
run, cancel, receipts, gates, secret presence, and file slots.

One place needed a new mechanism rather than a reuse. ``EventSource`` cannot
set an ``Authorization`` header, and the manager API is bearer-only, so the
log stream is reached with a **single-use, short-TTL stream ticket** in the URL
path. Putting the session bearer in a query string would have been simpler and
worse: query strings land in access logs and browser history, and that token
authorises every other endpoint. A ticket is bound to one run, dies on first
use, and grants nothing else.
"""
from __future__ import annotations

import asyncio
import json
import os
import secrets
import time
from datetime import datetime, timezone
from ipaddress import ip_address
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from server.backend.federation_manager import SessionManager, read_only_inventory
from server.backend.federation_manager_files import FileTokenBroker, FileTokenError
from server.backend.federation_manager_operations import (
    OperationDisabledError,
    OperationPolicyError,
    ParameterValidationError,
    PathContainmentError,
    accounting_summary,
)
from server.backend.federation_manager_receipts import ReceiptError, summarize
from server.backend.federation_manager_runner import RunRefused
from server.backend.federation_manager_secrets import SecretAccessError
from server.backend.federation_manager_transactions import TransactionError

router = APIRouter(prefix="/api/federation-manager", tags=["federation-manager"])

ALLOWED_ORIGINS = {
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
}
_bootstrap_nonce = os.environ.get("PRII_MANAGER_BOOTSTRAP_NONCE", "")
sessions = SessionManager(_bootstrap_nonce, ALLOWED_ORIGINS, ttl_seconds=300)

#: Populated by the native host at startup. When absent every operations
#: endpoint reports 503 rather than half-working, so a misconfigured deployment
#: fails visibly instead of silently offering controls that cannot run.
runtime: Optional["ManagerRuntime"] = None

STREAM_TICKET_TTL_SECONDS = 30.0
_stream_tickets: Dict[str, tuple[str, float]] = {}


class ManagerRuntime:
    """Everything the operations endpoints need, assembled by the native host."""

    def __init__(
        self,
        runner,
        files: FileTokenBroker,
        secrets_broker,
        gate_rules=(),
        *,
        repositories=None,
        artifacts=None,
        repository_binding_failures=None,
    ):
        self.runner = runner
        self.files = files
        self.secrets = secrets_broker
        self.gate_rules = list(gate_rules)
        self.repositories = repositories
        self.artifacts = artifacts
        self.repository_binding_failures = dict(repository_binding_failures or {})


# ── request bodies ──────────────────────────────────────────────────────────


class SessionRequest(BaseModel):
    nonce: str = Field(min_length=32)
    origin: str


class PlanRequest(BaseModel):
    parameters: Optional[Dict[str, Any]] = None


class RunRequest(BaseModel):
    parameters: Optional[Dict[str, Any]] = None
    file_tokens: Optional[Dict[str, str]] = None
    acknowledged: bool = False


class SecretRequest(BaseModel):
    app_id: str
    secret_id: str = Field(min_length=1, max_length=128)
    value: str = Field(min_length=1)


class SecretPresenceRequest(BaseModel):
    app_id: str
    secret_ids: List[str]


class FileSlotRequest(BaseModel):
    """A native pick. ``path`` is supplied by the native host, never the browser."""

    app_id: str
    path: str
    family: Optional[str] = None


# ── authorization ───────────────────────────────────────────────────────────


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


def _authorize(request: Request, authorization: Optional[str]) -> str:
    """Run the three-gate chain and return the validated session token."""
    _require_loopback(request)
    origin = _origin(request)
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="manager session required")
    token = authorization[7:]
    if not sessions.validate(token, origin):
        raise HTTPException(status_code=401, detail="manager session invalid or expired")
    return token


def _require_runtime() -> "ManagerRuntime":
    if runtime is None:
        raise HTTPException(
            status_code=503,
            detail="operations runtime is not configured; start the manager through the native host",
        )
    return runtime


def _operation_error(exc: Exception) -> HTTPException:
    """Map a domain failure to a status a client can act on.

    A disabled operation is 409 rather than 404: it exists and is described in
    the policy, and telling the operator "not found" would send them looking
    for a typo instead of reading the reason it is disabled.
    """
    if isinstance(exc, OperationDisabledError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, (ParameterValidationError, PathContainmentError, RunRefused)):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, FileTokenError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, SecretAccessError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, TransactionError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, OperationPolicyError):
        return HTTPException(status_code=404, detail=str(exc))
    raise exc


# ── session and inventory (Phase 1 surface, unchanged) ──────────────────────


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
def list_apps(request: Request, authorization: Optional[str] = Header(None)):
    _authorize(request, authorization)
    return read_only_inventory()


@router.get("/apps/{app_id}")
def get_app(app_id: str, request: Request, authorization: Optional[str] = Header(None)):
    _authorize(request, authorization)
    for app in read_only_inventory():
        if app["appId"] == app_id:
            return app
    raise HTTPException(status_code=404, detail="unknown app")


# ── operations ──────────────────────────────────────────────────────────────


@router.get("/operations")
def list_operations(request: Request, authorization: Optional[str] = Header(None)):
    """Every declared operation, enabled or not, with the reason when not.

    Deferred operations are returned rather than hidden so the UI can show an
    honest, complete inventory with explanations instead of a short list that
    looks like the whole story.
    """
    _authorize(request, authorization)
    active = _require_runtime()
    payload = []
    for operation in active.runner.policy.operations.values():
        payload.append(
            {
                "operationId": operation.operation_id,
                "appId": operation.app_id,
                "repo": operation.repo,
                "category": operation.category,
                "enabled": operation.enabled,
                "enablementReason": operation.enablement_reason,
                "riskClass": operation.risk_class,
                "approvalPolicy": operation.approval_policy,
                "networkPolicy": operation.network_policy,
                "writeScope": operation.write_scope,
                "rollbackStrategy": operation.rollback_strategy,
                "targetKind": operation.target.kind,
                "parameters": dict(operation.parameters),
                "secretRefs": list(operation.secret_refs),
                "expectedOutputs": list(operation.expected_outputs),
            }
        )
    payload.sort(key=lambda item: item["operationId"])
    return payload


@router.get("/operations/accounting")
def operations_accounting(request: Request, authorization: Optional[str] = Header(None)):
    _authorize(request, authorization)
    active = _require_runtime()
    policy = active.runner.policy
    return {
        "policyId": policy.policy_id,
        "sequence": policy.sequence,
        "payloadSha256": policy.payload_sha256,
        "keyId": policy.key_id,
        "expiresAt": policy.expires_at,
        **accounting_summary(
            {
                "policy": {
                    "operations": [
                        {
                            "operation_id": op.operation_id,
                            "app_id": op.app_id,
                            "enablement": op.enablement,
                            "enablement_reason": op.enablement_reason,
                        }
                        for op in policy.operations.values()
                    ]
                }
            }
        ),
    }


@router.get("/apps/{app_id}/prerequisites")
def app_prerequisites(
    app_id: str, request: Request, authorization: Optional[str] = Header(None)
):
    """Machine-detected prerequisites for one application."""
    _authorize(request, authorization)
    active = _require_runtime()
    return active.runner.prerequisites(app_id)


@router.post("/operations/{operation_id}/plan")
def plan_operation(
    operation_id: str,
    body: PlanRequest,
    request: Request,
    authorization: Optional[str] = Header(None),
):
    token = _authorize(request, authorization)
    active = _require_runtime()
    try:
        plan = active.runner.plan(operation_id, body.parameters, session_token=token)
    except Exception as exc:  # noqa: BLE001 - mapped to a status below
        raise _operation_error(exc) from exc
    return plan.as_dict()


@router.post("/operations/{operation_id}/run")
async def run_operation(
    operation_id: str,
    body: RunRequest,
    request: Request,
    authorization: Optional[str] = Header(None),
):
    """Execute an operation and return its signed receipt.

    Runs in a worker thread: the executor is blocking by nature (it supervises
    a child process and streams its output), and holding the event loop would
    stall every other manager request including the cancel endpoint.
    """
    token = _authorize(request, authorization)
    active = _require_runtime()

    try:
        operation = active.runner.policy.require(operation_id)
    except Exception as exc:  # noqa: BLE001
        raise _operation_error(exc) from exc

    if operation.approval_policy != "none" and not body.acknowledged:
        raise HTTPException(
            status_code=428,
            detail=(
                f"operation requires explicit acknowledgement: {operation.approval_policy}"
            ),
        )

    try:
        document = await asyncio.to_thread(
            active.runner.run,
            operation_id,
            body.parameters,
            session_token=token,
            file_tokens=body.file_tokens,
        )
    except Exception as exc:  # noqa: BLE001
        raise _operation_error(exc) from exc
    return document


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str, request: Request, authorization: Optional[str] = Header(None)):
    _authorize(request, authorization)
    active = _require_runtime()
    if not active.runner.cancel(run_id):
        raise HTTPException(status_code=409, detail="run is not active")
    return {"runId": run_id, "cancelled": True}


@router.get("/runs/{run_id}/receipt")
def get_receipt(run_id: str, request: Request, authorization: Optional[str] = Header(None)):
    _authorize(request, authorization)
    active = _require_runtime()
    try:
        return active.runner.receipts.load(run_id)
    except ReceiptError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/receipts")
def list_receipts(request: Request, authorization: Optional[str] = Header(None)):
    _authorize(request, authorization)
    active = _require_runtime()
    documents = active.runner.receipts.all_documents()
    return {
        "chainProblems": active.runner.receipts.verify_chain(),
        "receipts": [
            {
                "runId": d["receipt"]["run_id"],
                "operationId": d["receipt"]["operation_id"],
                "appId": d["receipt"]["app_id"],
                "status": d["receipt"]["status"],
                "finishedAt": d["receipt"]["finished_at"],
                "receiptSha256": d["signature"]["payload_sha256"],
            }
            for d in documents
        ],
    }


@router.get("/gates")
def get_gates(request: Request, authorization: Optional[str] = Header(None)):
    """Machine-derived gate status. Never accepts a status from a client."""
    _authorize(request, authorization)
    active = _require_runtime()
    from server.backend.federation_manager_receipts import evaluate_gates

    evidence = evaluate_gates(
        active.gate_rules,
        active.runner.receipts.all_documents(),
        public_key_pem=active.runner.receipts.signer.public_key_pem(),
        policy_sha256=active.runner.policy.payload_sha256,
    )
    return {"summary": summarize(evidence), **evidence}


# ── secrets: presence in, no values out ─────────────────────────────────────


@router.post("/secrets")
def set_secret(body: SecretRequest, request: Request, authorization: Optional[str] = Header(None)):
    _authorize(request, authorization)
    active = _require_runtime()
    try:
        active.secrets.set(body.app_id, body.secret_id, body.value)
    except SecretAccessError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    # Echo presence, never the value -- not even a length or a masked prefix.
    return active.secrets.validate(body.app_id, body.secret_id)


@router.post("/secrets/presence")
def secret_presence(
    body: SecretPresenceRequest, request: Request, authorization: Optional[str] = Header(None)
):
    _authorize(request, authorization)
    active = _require_runtime()
    return active.secrets.presence(body.app_id, body.secret_ids)


@router.delete("/secrets/{app_id}/{secret_id}")
def delete_secret(
    app_id: str, secret_id: str, request: Request, authorization: Optional[str] = Header(None)
):
    _authorize(request, authorization)
    active = _require_runtime()
    try:
        active.secrets.delete(app_id, secret_id)
    except SecretAccessError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"secretId": secret_id, "status": "absent"}


# ── file slots ──────────────────────────────────────────────────────────────


@router.post("/files/slots")
def create_file_slot(
    body: FileSlotRequest, request: Request, authorization: Optional[str] = Header(None)
):
    """Register a natively-picked file and return an opaque token.

    The ``path`` in the body comes from the native picker on the same loopback
    host, not from a browser file input. The response deliberately contains no
    path: everything downstream refers to the file by token.
    """
    token = _authorize(request, authorization)
    active = _require_runtime()
    try:
        file_token = active.files.mint(
            session_token=token,
            app_id=body.app_id,
            source_path=Path(body.path),
            family=body.family,
        )
    except FileTokenError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"fileToken": file_token, "appId": body.app_id, "family": body.family}


@router.delete("/files/slots/{file_token}")
def revoke_file_slot(
    file_token: str, request: Request, authorization: Optional[str] = Header(None)
):
    _authorize(request, authorization)
    active = _require_runtime()
    active.files.revoke(file_token)
    return {"revoked": True}


# ── log streaming ───────────────────────────────────────────────────────────


def _purge_tickets(now: float) -> None:
    for ticket, (_, expires) in list(_stream_tickets.items()):
        if now >= expires:
            _stream_tickets.pop(ticket, None)


@router.post("/runs/{run_id}/log-ticket")
def create_log_ticket(run_id: str, request: Request, authorization: Optional[str] = Header(None)):
    """Mint a single-use ticket for the SSE log stream.

    EventSource cannot send an Authorization header, so the stream is reached
    by a path-embedded ticket instead. The ticket is bound to one run, expires
    in seconds, and is consumed on first use -- so a leaked URL grants a
    replayable capability to nothing.
    """
    _authorize(request, authorization)
    _require_runtime()
    now = time.time()
    _purge_tickets(now)
    ticket = secrets.token_urlsafe(32)
    _stream_tickets[ticket] = (run_id, now + STREAM_TICKET_TTL_SECONDS)
    return {"ticket": ticket, "expiresInSeconds": STREAM_TICKET_TTL_SECONDS}


@router.get("/runs/{run_id}/logs/{ticket}")
async def stream_logs(run_id: str, ticket: str, request: Request):
    """Server-sent redacted log lines for one run.

    No bearer here by necessity; the ticket is the credential, and loopback and
    origin are still enforced.
    """
    _require_loopback(request)
    active = _require_runtime()

    now = time.time()
    _purge_tickets(now)
    record = _stream_tickets.pop(ticket, None)  # single use
    if record is None or record[0] != run_id:
        raise HTTPException(status_code=403, detail="invalid or expired stream ticket")

    handle = active.runner.handle(run_id)
    if handle is None:
        raise HTTPException(status_code=404, detail="unknown run")

    async def events():
        emitted = 0
        while True:
            if await request.is_disconnected():
                return
            while emitted < len(handle.lines):
                line = handle.lines[emitted]
                emitted += 1
                yield f"data: {json.dumps({'line': line})}\n\n"
            if handle.finished.is_set() and emitted >= len(handle.lines):
                yield f"data: {json.dumps({'status': handle.status, 'done': True})}\n\n"
                return
            await asyncio.sleep(0.1)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.get("/runs/{run_id}/logs")
def get_log_snapshot(run_id: str, request: Request, authorization: Optional[str] = Header(None)):
    """Non-streaming fallback, for clients without EventSource."""
    _authorize(request, authorization)
    active = _require_runtime()
    handle = active.runner.handle(run_id)
    if handle is None:
        raise HTTPException(status_code=404, detail="unknown run")
    return {
        "runId": run_id,
        "status": handle.status,
        "done": handle.finished.is_set(),
        "lines": list(handle.lines),
    }
