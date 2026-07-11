import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from hub.mcp_runtime import Router, RuntimeRegistry  # noqa: E402
from hub.mcp_runtime.adapters import (  # noqa: E402
    ContractsAdapter,
    GeospatialAdapter,
)
from server.backend.mcp_api import build_mcp_api  # noqa: E402


class FakeClient:
    def __init__(self, payload):
        self.payload = payload

    def get(self, url, params=None):
        return self.payload


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.delenv("MCP_CONTRACTS_API_KEY", raising=False)
    router = Router(RuntimeRegistry())
    router.register_adapter(GeospatialAdapter())
    router.register_adapter(ContractsAdapter(client=FakeClient({})))
    app = FastAPI()
    app.include_router(build_mcp_api(router))
    return TestClient(app)


def test_route_happy_path(client):
    resp = client.post("/mcp/route", json={
        "project": "spiderweb", "capability": "geospatial", "action": "distance",
        "params": {"a": [18.46, -66.10], "b": [18.01, -66.61]},
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "distance_km" in body["data"]
    assert body["provenance"]["version_pin"] == "1.0.0"


def test_route_forbidden_when_not_declared(client):
    # spiderweb does not declare contracts
    resp = client.post("/mcp/route", json={
        "project": "spiderweb", "capability": "contracts", "action": "search",
        "params": {"keyword": "x"},
    })
    assert resp.status_code == 403


def test_route_bad_action_is_400(client):
    resp = client.post("/mcp/route", json={
        "project": "spiderweb", "capability": "geospatial", "action": "bogus",
    })
    assert resp.status_code == 400


def test_route_missing_credential_is_401(client):
    # moneysweep declares contracts, but no API key is configured -> fail closed
    resp = client.post("/mcp/route", json={
        "project": "moneysweep", "capability": "contracts", "action": "search",
        "params": {"keyword": "recovery", "posted_from": "01/01/2026",
                   "posted_to": "03/01/2026"},
    })
    assert resp.status_code == 401


def test_health_and_ready(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {"status": "ready"}


def test_capabilities_lists_registry(client):
    body = client.get("/mcp/capabilities").json()
    assert len(body["capabilities"]) == 12
    assert body["capabilities"]["federation-core"]["version_pin"] == "1.0.0"
    assert "moneysweep" in body["projects"]
