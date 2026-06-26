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
from fastapi.responses import Response

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
    "water_grid_monitoring_node": "Infrastructure",
    "anomaly_intelligence_node": "UAP",
    "airspace_intelligence_node": "Airspace",
}

_DISPLAY_NAMES = {
    "moneysweep-pr": "MoneySweep PR",
    "spiderweb-pr": "Spiderweb PR",
    "aguayluz-pr": "AguaYLuz PR",
    "ovnis-pr": "OVNIS PR",
    "skywatcher-pr": "Skywatcher PR",
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

# ── Generic entity CRUD ────────────────────────────────────────────────────────

@app.get("/api/entities/{entity_name}")
def list_entities(entity_name: str, sort: str = Query("-created_date"), limit: int = Query(500)):
    c = _conn()
    rows = c.execute(
        "SELECT data, updated_at, entity_id FROM entities WHERE entity_type=? LIMIT ?",
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

    c = _conn()
    rows = c.execute(
        "SELECT data, updated_at, entity_id FROM entities WHERE entity_type=? LIMIT ?",
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

# ── Stub endpoints for optional features ──────────────────────────────────────

@app.api_route("/api/functions/{function_name}/invoke", methods=["POST"])
async def invoke_function(function_name: str, request: Request):
    return {"result": None, "message": f"Function {function_name!r} not implemented"}


@app.api_route("/api/agents/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def agents_stub(path: str, request: Request):
    if request.method == "GET":
        return []
    return {"id": str(uuid.uuid4()), "message": "Agents not implemented in diagnostic mode"}


@app.api_route("/api/integrations/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def integrations_stub(path: str, request: Request):
    return {"message": f"Integration {path!r} not configured"}


@app.post("/api/files/upload")
async def files_upload():
    return {"file_id": str(uuid.uuid4()), "message": "File storage not implemented"}


@app.get("/api/connectors/{name}/connection")
def connectors_stub(name: str):
    return {"status": "not_connected", "name": name}
