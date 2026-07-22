"""Tests for the same-origin desktop app server (SPA fallback + API precedence).

Ported from the per-repo ``tests/test_desktop_app_server.py``. Covers the
behaviours that regressed: SPA navigation on API-shadowed paths, API priority for
fetch()-style requests, passthrough prefixes, the trailing-slash redirect,
static-asset serving, the path-traversal guard, and the friendly missing-build
page. Exercised against a minimal FastAPI app (no producer backend needed).
Skipped when fastapi/httpx aren't installed.
"""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi import FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from prii_desktop import attach_spa  # noqa: E402


def _minimal_app():
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"ok": True}

    return app


@pytest.fixture
def built_client(tmp_path):
    """A client whose dist dir contains a built frontend."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>app</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    app = attach_spa(_minimal_app(), dist)
    with TestClient(app) as client:
        yield client


def test_spa_navigation_serves_index(built_client):
    r = built_client.get("/deep/client/route", headers={"accept": "text/html"})
    assert r.status_code == 200
    assert "<title>app</title>" in r.text


def test_spa_navigation_on_api_shadowed_path(built_client):
    # A browser navigation to a path that also exists as an API endpoint
    # (/health) must return the SPA, not the JSON — the /sources-style regression.
    r = built_client.get("/health", headers={"accept": "text/html"})
    assert "text/html" in r.headers["content-type"]


def test_api_keeps_priority_for_fetch(built_client):
    r = built_client.get("/health", headers={"accept": "*/*"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")


def test_docs_not_hijacked(built_client):
    r = built_client.get("/openapi.json", headers={"accept": "text/html"})
    assert r.headers["content-type"].startswith("application/json")


def test_trailing_slash_redirects_api(built_client):
    r = built_client.get("/health/", headers={"accept": "*/*"}, follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/health"


def test_static_asset_served(built_client):
    r = built_client.get("/assets/app.js")
    assert r.status_code == 200
    assert "console.log" in r.text


def test_path_traversal_falls_back_to_index(built_client):
    r = built_client.get("/../../etc/passwd", headers={"accept": "text/html"})
    assert r.status_code == 200
    assert "<title>app</title>" in r.text  # never serves outside the dist dir


def test_missing_build_shows_setup_page(tmp_path):
    app = attach_spa(_minimal_app(), tmp_path / "nope")
    with TestClient(app) as client:
        r = client.get("/", headers={"accept": "text/html"})
    assert r.status_code == 503
    assert "desktop/setup.py" in r.text
