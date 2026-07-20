"""
TheHub PRII Federation API — FastAPI server.

Generic SQLite-backed entity store that implements the INTSYS-PR federation
contract: /api/entities/{entityName} CRUD + /api/apps/public-settings + /api/auth/me.

Start with:
    python -m uvicorn server.backend.main:app --port 8000
(from the thehub-pr repo root, with the server optional-deps installed)
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

REPO_ROOT = Path(__file__).parent.parent.parent
DB_PATH = REPO_ROOT / "data" / "hub.db"
REGISTRY_PATH = REPO_ROOT / "registry" / "producers.yaml"

# ── Lifecycle ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_db()
    _seed_programs()
    yield


app = FastAPI(title="TheHub PRII Federation API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── DB helpers ─────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = _conn()
    c.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            entity_type TEXT NOT NULL,
            entity_id   TEXT NOT NULL,
            data        TEXT NOT NULL,
            updated_at  TEXT NOT NULL,
            PRIMARY KEY (entity_type, entity_id)
        )
    """)
    c.commit()
    c.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row(row: sqlite3.Row) -> dict[str, Any]:
    d = json.loads(row["data"])
    d.setdefault("id", row["entity_id"])
    d.setdefault("created_date", row["updated_at"])
    d.setdefault("updated_date", row["updated_at"])
    return d

# ── Seed ──────────────────────────────────────────────────────────────────────

_DOMAIN_MAP = {
    "public_money_intelligence_node": "Contracts",
    "spatial_operational_query_hub": "NetworkGraph",
    "spatial_operational_producer": "NetworkGraph",
    "water_grid_monitoring_node": "Infrastructure",
    "anomaly_intelligence_node": "UAP",
    "airspace_intelligence_node": "Airspace",
    "pre_officialization_signal_producer": "Signals",
}

_DISPLAY_NAMES = {
    "moneysweep-pr": "MoneySweep PR",
    "spiderweb-pr": "Spiderweb PR",
    "aguayluz-pr": "AguaYLuz PR",
    "ovnis-pr": "OVNIS PR",
    "skywatcher-pr": "Skywatcher PR",
    "centinelas-pr": "Centinelas PR",
}


def _seed_programs() -> None:
    if not REGISTRY_PATH.exists():
        return
    with open(REGISTRY_PATH) as f:
        registry = yaml.safe_load(f)

    c = _conn()
    ts = _now()
    for p in registry.get("producers", []):
        pid = p["program_id"]
        if c.execute(
            "SELECT 1 FROM entities WHERE entity_type='Programs' AND entity_id=?", (pid,)
        ).fetchone():
            continue

        status = p.get("status", "ready_for_discovery")
        row: dict[str, Any] = {
            "id": pid,
            "program_id": pid,
            "name": _DISPLAY_NAMES.get(pid, pid),
            "repo_name": p.get("repo", ""),
            "domain": _DOMAIN_MAP.get(p.get("role", ""), "ControlPlane"),
            "status": "Active",
            "lead_vector": p.get("role", ""),
            "github_sync_status": "Ready" if "ready" in status else "NotConnected",
            "federation_status": status,
            "description": f"Federation producer node: {p.get('role', '')}",
            "created_date": ts,
            "updated_date": ts,
        }
        c.execute(
            "INSERT OR IGNORE INTO entities (entity_type, entity_id, data, updated_at) VALUES (?,?,?,?)",
            ("Programs", pid, json.dumps(row), ts),
        )
    c.commit()
    c.close()

# ── System / health ────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    c = _conn()
    row = c.execute("SELECT COUNT(*) as n FROM entities").fetchone()
    n = row["n"] if row else 0
    c.close()
    return {"status": "ok", "entity_count": n}


@app.get("/api/health")
def api_health():
    return health()


@app.get("/api/apps/public-settings")
def public_settings():
    return {
        "id": "thehub-pr",
        "name": "TheHub — PRII Federation Control Plane",
        "public_settings": {"requires_auth": False, "mode": "diagnostic"},
    }


@app.get("/api/auth/me")
def auth_me():
    raise HTTPException(status_code=401, detail="No auth in diagnostic mode")

# ── Notifications ───────────────────────────────────────────────────────────────
# "What's new since you last looked" + per-subscriber push/SMS preferences. The
# decision logic lives in server/backend/notifications.py (pure, unit-tested); these
# routes are the thin HTTP surface. Single-operator by default (subscriber_id
# "operator"), consistent with the diagnostic no-auth mode, but the store is keyed by
# subscriber so it extends to real multi-user auth without a schema change.
from server.backend import notifications as _notif  # noqa: E402

_ALERT_COLLECTION = "GovernanceAlerts"


def _load_alerts() -> list[dict[str, Any]]:
    c = _conn()
    rows = c.execute(
        "SELECT data, updated_at, entity_id FROM entities WHERE entity_type=? "
        "ORDER BY updated_at DESC LIMIT 2000",
        (_ALERT_COLLECTION,),
    ).fetchall()
    c.close()
    return [_row(r) for r in rows]


@app.get("/api/notifications")
def notifications(since: str | None = Query(None), subscriber: str = Query("operator")):
    """New alerts since ``since`` (or the subscriber's stored cursor), ranked."""
    c = _conn()
    store = _notif.NotificationStore(c)
    cursor = since if since is not None else store.get_cursor(subscriber)
    c.close()
    fresh = _notif.rank_new_alerts(_load_alerts(), cursor)
    return {
        "cursor": cursor,
        "count": len(fresh),
        "critical_count": sum(1 for a in fresh if a.get("is_critical")),
        "items": fresh,
    }


@app.post("/api/notifications/ack")
async def notifications_ack(request: Request):
    """Advance the subscriber's last-seen cursor (marks the digest read)."""
    body = await request.json()
    subscriber = body.get("subscriber", "operator")
    last_seen = body.get("last_seen") or _now()
    c = _conn()
    _notif.NotificationStore(c).set_cursor(last_seen, subscriber)
    c.close()
    return {"subscriber": subscriber, "last_seen": last_seen}


@app.get("/api/notifications/preferences")
def get_preferences(subscriber: str = Query("operator")):
    c = _conn()
    sub = _notif.NotificationStore(c).get_subscription(subscriber)
    c.close()
    return {"subscriber": subscriber, **sub, "domains": sorted(set(_notif.DOMAIN_FOR_MODULE.values())),
            "channels": list(_notif.VALID_CHANNELS), "timing": list(_notif.VALID_TIMING)}


@app.put("/api/notifications/preferences")
async def set_preferences(request: Request):
    """Set channel (push/sms/none) + timing (asap/brief) prefs, global or per-domain."""
    body = await request.json()
    subscriber = body.get("subscriber", "operator")
    prefs = body.get("prefs", {})
    targets = body.get("targets", {})
    c = _conn()
    _notif.NotificationStore(c).set_subscription(prefs, targets, subscriber, _now())
    c.close()
    return {"subscriber": subscriber, "prefs": prefs, "targets": targets}

# ── Generic entity CRUD ────────────────────────────────────────────────────────

@app.get("/api/entities/{entity_name}")
def list_entities(entity_name: str, sort: str = Query("-created_date"), limit: int = Query(500)):
    # Order by the write timestamp before applying LIMIT so a bounded page returns
    # the most-recently-touched rows rather than an arbitrary slice — otherwise, past
    # `limit` rows, genuinely-new items can be dropped before the client re-sorts.
    # `sort` is a "-field"/"field" recency hint; only its leading sign is honored here
    # (all fields collapse to updated_at, the indexed write time). `direction` is a
    # validated literal, so interpolating it into the query is injection-safe.
    direction = "ASC" if sort and not sort.startswith("-") else "DESC"
    c = _conn()
    rows = c.execute(
        f"SELECT data, updated_at, entity_id FROM entities WHERE entity_type=? "
        f"ORDER BY updated_at {direction} LIMIT ?",
        (entity_name, limit),
    ).fetchall()
    c.close()
    return [_row(r) for r in rows]


@app.post("/api/entities/{entity_name}")
async def create_entity(entity_name: str, request: Request):
    body = await request.json()
    ts = _now()
    entity_id = (
        body.get("id")
        or body.get(f"{entity_name.rstrip('s').lower()}_id")
        or body.get("program_id")
        or str(uuid.uuid4())
    )
    body.setdefault("id", entity_id)
    body.setdefault("created_date", ts)
    body["updated_date"] = ts

    c = _conn()
    c.execute(
        "INSERT INTO entities (entity_type, entity_id, data, updated_at) VALUES (?,?,?,?)",
        (entity_name, entity_id, json.dumps(body), ts),
    )
    c.commit()
    c.close()
    return body


@app.get("/api/entities/{entity_name}/{entity_id}")
def get_entity(entity_name: str, entity_id: str):
    c = _conn()
    row = c.execute(
        "SELECT data, updated_at, entity_id FROM entities WHERE entity_type=? AND entity_id=?",
        (entity_name, entity_id),
    ).fetchone()
    c.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"{entity_name}/{entity_id} not found")
    return _row(row)


@app.patch("/api/entities/{entity_name}/{entity_id}")
async def update_entity(entity_name: str, entity_id: str, request: Request):
    patch = await request.json()
    c = _conn()
    row = c.execute(
        "SELECT data, updated_at, entity_id FROM entities WHERE entity_type=? AND entity_id=?",
        (entity_name, entity_id),
    ).fetchone()
    if not row:
        c.close()
        raise HTTPException(status_code=404, detail=f"{entity_name}/{entity_id} not found")

    data = json.loads(row["data"])
    data.update(patch)
    ts = _now()
    data["updated_date"] = ts
    c.execute(
        "UPDATE entities SET data=?, updated_at=? WHERE entity_type=? AND entity_id=?",
        (json.dumps(data), ts, entity_name, entity_id),
    )
    c.commit()
    c.close()
    return data


@app.delete("/api/entities/{entity_name}/{entity_id}", status_code=204)
def delete_entity(entity_name: str, entity_id: str):
    c = _conn()
    c.execute(
        "DELETE FROM entities WHERE entity_type=? AND entity_id=?",
        (entity_name, entity_id),
    )
    c.commit()
    c.close()
    return Response(status_code=204)


@app.post("/api/entities/{entity_name}/filter")
async def filter_entities(entity_name: str, request: Request):
    body = await request.json()
    filters: dict = body.get("filters", {})
    limit: int = body.get("limit", 500)
    sort: str = body.get("sort") or "-created_date"

    c = _conn()
    # Order by write time before the (oversized) prefetch cap so the Python-side filter
    # scans the right end of the range — otherwise, past the cap, matching rows can be
    # missed. Honor the caller's requested direction (as list_entities does) so ascending
    # requests (e.g. chronological chat transcripts) aren't silently reversed.
    direction = "ASC" if not sort.startswith("-") else "DESC"
    rows = c.execute(
        f"SELECT data, updated_at, entity_id FROM entities WHERE entity_type=? "
        f"ORDER BY updated_at {direction} LIMIT ?",
        (entity_name, max(limit * 10, 5000)),
    ).fetchall()
    c.close()

    results = []
    for r in rows:
        d = _row(r)
        if all(d.get(k) == v for k, v in filters.items()):
            results.append(d)
        if len(results) >= limit:
            break
    return results


@app.post("/api/entities/{entity_name}/bulk")
async def bulk_create(entity_name: str, request: Request):
    body = await request.json()
    items: list = body.get("items", [])
    ts = _now()
    c = _conn()
    created = []
    for item in items:
        entity_id = item.get("id") or str(uuid.uuid4())
        item.setdefault("id", entity_id)
        item.setdefault("created_date", ts)
        item["updated_date"] = ts
        c.execute(
            "INSERT OR REPLACE INTO entities (entity_type, entity_id, data, updated_at) VALUES (?,?,?,?)",
            (entity_name, entity_id, json.dumps(item), ts),
        )
        created.append(item)
    c.commit()
    c.close()
    return created

# ── Diagnostic-mode stub endpoints ─────────────────────────────────────────────
# These three subsystems (function execution, conversational agents, binary file
# storage) are intentionally NOT implemented in this hub build. They are bound to
# live producer feeds / external backends that are out of local scope, so the hub
# ships them as *diagnostic-mode stubs* rather than fabricating real behaviour.
#
# Each returns an explicit, self-documenting payload carrying a stable, machine-
# readable contract: `status="not_implemented"`, `mode="diagnostic"`,
# `implemented=False`, a `feature` name, and a documented `reason`. The HTTP status
# is deliberately kept at 200 (not 501): the single-product frontend treats any
# non-2xx response as a hard error, and these stubs must let the diagnostic UI stay
# functional (degrading gracefully) instead of throwing. Compatibility keys the
# frontend reads (e.g. `id` for a created agent conversation) are preserved.

DIAGNOSTIC_STUB_REASONS: dict[str, str] = {
    "functions": (
        "Federation function execution is bound to live producer feeds and is "
        "disabled in the diagnostic-mode hub build."
    ),
    "agents": (
        "The conversational agents subsystem is not provisioned in diagnostic "
        "mode; it activates only with a configured agent backend."
    ),
    "files": (
        "Binary file storage is not provisioned in diagnostic mode; this hub "
        "build retains no upload backend."
    ),
}


def _diagnostic_stub(feature: str, **extra: Any) -> dict[str, Any]:
    """Build the stable diagnostic-mode contract for an unimplemented subsystem.

    The returned mapping always carries ``status``, ``mode``, ``implemented``,
    ``feature`` and ``reason`` keys; ``extra`` supplies endpoint-specific
    compatibility keys (e.g. ``id`` / ``result`` / ``file_id``) the frontend reads.
    """
    reason = DIAGNOSTIC_STUB_REASONS[feature]
    payload: dict[str, Any] = {
        "status": "not_implemented",
        "mode": "diagnostic",
        "implemented": False,
        "feature": feature,
        "reason": reason,
        "message": f"{feature} not implemented in diagnostic mode",
    }
    payload.update(extra)
    return payload


@app.api_route("/api/functions/{function_name}/invoke", methods=["POST"])
async def invoke_function(function_name: str, request: Request) -> dict[str, Any]:
    return _diagnostic_stub("functions", function=function_name, result=None)


@app.api_route("/api/agents/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def agents_stub(path: str, request: Request):
    if request.method == "GET":
        return []
    return _diagnostic_stub("agents", id=str(uuid.uuid4()))


@app.api_route("/api/integrations/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def integrations_stub(path: str, request: Request):
    return {"message": f"Integration {path!r} not configured"}


@app.post("/api/files/upload")
async def files_upload() -> dict[str, Any]:
    return _diagnostic_stub("files", file_id=str(uuid.uuid4()))


@app.get("/api/connectors/{name}/connection")
def connectors_stub(name: str):
    return {"status": "not_connected", "name": name}

# ── Static frontend (one served product) ───────────────────────────────────────
# When the frontend is built (`npm --prefix server/frontend run build`), serve it
# from the same origin as /api so the hub is a single deployable product. If dist/
# is absent (API-only dev, with Vite on :5173), these routes simply don't mount.
# Registered LAST, after every /api and /health route, so the catch-all never
# shadows an API route.

# ── MCP federation API ─────────────────────────────────────────────────────────
# Mount the runtime Router as HTTP routes. Guarded so a failure in the MCP layer
# can never take down the entity API. Registered before the SPA catch-all below
# so its GET routes (/healthz, /readyz, /mcp/capabilities) are not shadowed.
try:
    from server.backend.mcp_api import build_mcp_api, create_default_hub_router

    app.include_router(build_mcp_api(create_default_hub_router()))
except Exception as _mcp_exc:  # pragma: no cover - defensive mount guard
    import logging as _logging

    _logging.getLogger("hub.mcp").warning("MCP API not mounted: %s", _mcp_exc)

DIST = REPO_ROOT / "server" / "frontend" / "dist"

if DIST.is_dir():
    if (DIST / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        # Serve a real built file when it exists (favicon, etc.); otherwise the SPA
        # shell. /api/* is handled above; block it here so unknown API paths 404.
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (DIST / full_path).resolve()
        if full_path and candidate.is_file() and DIST.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(DIST / "index.html")
