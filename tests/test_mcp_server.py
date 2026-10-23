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
    return TestClient(app, client=("127.0.0.1", 8000))


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


def test_route_rejects_non_loopback_clients():
    router = Router(RuntimeRegistry())
    router.register_adapter(GeospatialAdapter())
    app = FastAPI()
    app.include_router(build_mcp_api(router))
    remote_client = TestClient(app, client=("198.51.100.7", 8000))

    response = remote_client.post("/mcp/route", json={
        "project": "spiderweb", "capability": "geospatial", "action": "distance",
        "params": {"a": [18.46, -66.10], "b": [18.01, -66.61]},
    })

    assert response.status_code == 403


def test_adapter_declared_write_requires_hub_write_authorizer():
    class WriteGeospatialAdapter(GeospatialAdapter):
        def write_actions(self):
            return ["distance"]

    router = Router(RuntimeRegistry())
    router.register_adapter(WriteGeospatialAdapter())
    app = FastAPI()
    app.include_router(build_mcp_api(router))
    local_client = TestClient(app, client=("127.0.0.1", 8000))

    response = local_client.post("/mcp/route", json={
        "project": "spiderweb", "capability": "geospatial", "action": "distance",
        "params": {"a": [18.46, -66.10], "b": [18.01, -66.61]},
    })

    assert response.status_code == 503
    assert response.json()["detail"] == "MCP write authorization is not configured"


def test_adapter_declared_write_calls_authorizer_even_when_request_flag_is_false():
    class WriteGeospatialAdapter(GeospatialAdapter):
        def write_actions(self):
            return ["distance"]

    authorized_requests = []
    router = Router(RuntimeRegistry())
    router.register_adapter(WriteGeospatialAdapter())
    app = FastAPI()
    app.include_router(
        build_mcp_api(
            router,
            write_authorizer=lambda request: authorized_requests.append(request),
        )
    )
    local_client = TestClient(app, client=("127.0.0.1", 8000))

    response = local_client.post("/mcp/route", json={
        "project": "spiderweb", "capability": "geospatial", "action": "distance",
        "params": {"a": [18.46, -66.10], "b": [18.01, -66.61]},
        "is_write": False,
    })

    assert len(authorized_requests) == 1
    assert response.status_code == 403


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
    assert len(body["capabilities"]) == 15
    assert body["capabilities"]["federation-core"]["version_pin"] == "1.0.0"
    assert body["capabilities"]["osha"]["class"] == "government"
    jp_flood = body["capabilities"]["jp-flood-certification"]
    assert jp_flood["class"] == "domain"
    assert jp_flood["status"] == "active"
    assert jp_flood["version_pin"] == "3.0.0"
    assert sorted(jp_flood["required_by"]) == ["aguayluz", "spiderweb"]
    intelligence_query = body["capabilities"]["intelligence-query"]
    assert intelligence_query["class"] == "core"
    assert intelligence_query["status"] == "pilot"
    assert intelligence_query["required_by"] == ["ovnis"]
    assert "moneysweep" in body["projects"]


def test_metrics_endpoint_reports_after_routes():
    from hub.mcp_runtime import InMemoryMetrics, ResponseCache, Router, RuntimeRegistry
    from hub.mcp_runtime.adapters import GeospatialAdapter

    router = Router(
        RuntimeRegistry(), metrics_sink=InMemoryMetrics(),
        cache=ResponseCache(ttl_seconds=30),
    )
    router.register_adapter(GeospatialAdapter())
    app = FastAPI()
    app.include_router(build_mcp_api(router))
    c = TestClient(app, client=("127.0.0.1", 8000))

    payload = {
        "project": "spiderweb", "capability": "geospatial", "action": "distance",
        "params": {"a": [18.46, -66.10], "b": [18.01, -66.61]},
    }
    c.post("/mcp/route", json=payload)
    c.post("/mcp/route", json=payload)  # cache hit
    agg = c.get("/mcp/metrics").json()
    assert agg["count"] == 2
    assert agg["cache_hit_rate"] == 0.5
