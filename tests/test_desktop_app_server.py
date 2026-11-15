"""Contract tests for TheHub's thin shared-runtime ASGI adapter.

SPA fallback behavior is exercised exhaustively by
``packages/prii_desktop/tests/test_appserver.py``. These tests keep the
producer boundary focused on TheHub's own launcher and API wiring.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("prii_desktop")

from fastapi.testclient import TestClient  # noqa: E402

import desktop.app_server as app_server  # noqa: E402


@pytest.fixture
def client():
    with TestClient(app_server.app) as test_client:
        yield test_client


def test_health_api_remains_available(client):
    response = client.get("/health", headers={"accept": "application/json"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


def test_launcher_route_is_attached(client):
    response = client.get("/launcher")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_local_federation_api_is_attached(client):
    response = client.get("/api/local/federation")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_adapter_keeps_runtime_configuration_private():
    assert not hasattr(app_server, "DIST_DIR")


_CATCH_ALL = "/{full_path:path}"


def _index_of(routes, predicate):
    return [i for i, r in enumerate(routes) if predicate(getattr(r, "path", ""))]


def test_prioritize_desktop_routes_moves_routes_ahead_of_catch_all():
    # Independent of whether the frontend dist exists on this machine, and of
    # whether FastAPI flattens include_router() into per-path routes.
    from fastapi import APIRouter, FastAPI

    stub = FastAPI()

    @stub.get(_CATCH_ALL)
    def spa(full_path: str):
        return {"spa": full_path}

    known = {id(route) for route in stub.router.routes}

    local = APIRouter(prefix="/api/local")

    @local.get("/ping")
    def ping():
        return {"local": True}

    stub.include_router(local)

    @stub.get("/launcher")
    def launcher():
        return {"launcher": True}

    assert TestClient(stub).get("/api/local/ping").json() == {"spa": "api/local/ping"}

    app_server._prioritize_desktop_routes(stub, known)

    client = TestClient(stub)
    assert client.get("/api/local/ping").json() == {"local": True}
    assert client.get("/launcher").json() == {"launcher": True}
    assert client.get("/anything/else").json() == {"spa": "anything/else"}
