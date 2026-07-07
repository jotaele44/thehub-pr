"""Tests for the hub's same-origin desktop app server.

thehub's FastAPI backend already ships its own SPA layer (an /assets mount and
a /{full_path:path} catch-all), so the desktop wrapper's contribution here is
the SPA-navigation middleware (browser text/html navigations → index / friendly
page) layered on top. These tests cover that middleware and API precedence;
the static-asset and trailing-slash cases are owned by the backend's own SPA
layer and are exercised there, not here. Skipped when fastapi/httpx are absent.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from starlette.testclient import TestClient  # noqa: E402

import desktop.app_server as app_server  # noqa: E402


@pytest.fixture
def built_client(tmp_path, monkeypatch):
    """A client whose DIST_DIR contains a built frontend (lifespan runs)."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        "<!doctype html><title>hub</title>", encoding="utf-8"
    )
    monkeypatch.setattr(app_server, "DIST_DIR", dist)
    with TestClient(app_server.app) as client:
        yield client


def test_spa_navigation_serves_index(built_client):
    r = built_client.get("/some/client/route", headers={"accept": "text/html"})
    assert r.status_code == 200
    assert "<title>hub</title>" in r.text


def test_spa_navigation_on_api_shadowed_path(built_client):
    # A browser navigation to a path that also exists as an API endpoint must
    # return the SPA, not JSON — the middleware runs before the API route.
    r = built_client.get("/health", headers={"accept": "text/html"})
    assert "text/html" in r.headers["content-type"]


def test_api_keeps_priority_for_fetch(built_client):
    r = built_client.get("/health", headers={"accept": "*/*"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")


def test_auth_me_unauthenticated(built_client):
    # Anonymous local mode: /api/auth/me returns 401 and the frontend copes.
    assert built_client.get("/api/auth/me").status_code == 401


def test_launcher_not_hijacked(built_client):
    # /launcher and /api/local are in the passthrough set, so a text/html GET
    # is not rewritten to the dashboard SPA.
    r = built_client.get("/launcher", headers={"accept": "text/html"})
    assert r.status_code == 200


def test_missing_build_shows_setup_page(tmp_path, monkeypatch):
    monkeypatch.setattr(app_server, "DIST_DIR", tmp_path / "nope")
    with TestClient(app_server.app) as client:
        r = client.get("/x/y/z", headers={"accept": "text/html"})
    assert r.status_code == 503
    assert "desktop/setup.py" in r.text
