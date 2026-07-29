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

from starlette.testclient import TestClient  # noqa: E402

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


def test_local_setup_api_is_attached():
    paths = {route.path for route in app_server.app.routes}
    assert "/api/local/setup/status" in paths
    assert "/api/local/setup/save" in paths
    assert "/api/local/setup/repair" in paths
    assert "/api/local/setup/diagnostics" in paths


def test_adapter_keeps_runtime_configuration_private():
    assert not hasattr(app_server, "DIST_DIR")
