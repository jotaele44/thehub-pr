"""Contract tests for the hub's diagnostic-mode stub endpoints.

Three subsystems — federation function execution, conversational agents, and
binary file storage — are intentionally *not* implemented in this hub build.
They ship as diagnostic-mode stubs bound to live producer feeds / external
backends that are out of local scope.

These tests pin the documented diagnostic-mode contract so the stubs cannot
silently drift into fabricating "implemented" behaviour, and so the single-
product frontend keeps receiving a graceful (2xx) response it can render.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from server.backend.main import app  # noqa: E402


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _assert_diagnostic_contract(body: dict, feature: str) -> None:
    """Every diagnostic-mode stub must expose this stable, documented shape."""
    assert body["status"] == "not_implemented"
    assert body["mode"] == "diagnostic"
    assert body["implemented"] is False
    assert body["feature"] == feature
    # A documented, non-empty human-readable reason must always be present.
    assert isinstance(body.get("reason"), str) and body["reason"].strip()
    assert "diagnostic mode" in body["message"]


def test_function_invoke_returns_diagnostic_contract(client):
    resp = client.post("/api/functions/refetchUSASpending/invoke", json={"limit": 5})
    assert resp.status_code == 200
    body = resp.json()
    _assert_diagnostic_contract(body, "functions")
    # Compat keys the frontend reads must be preserved and must not fabricate work.
    assert body["function"] == "refetchUSASpending"
    assert body["result"] is None


def test_agents_create_returns_diagnostic_contract(client):
    resp = client.post("/api/agents/conversations", json={"title": "x"})
    assert resp.status_code == 200
    body = resp.json()
    _assert_diagnostic_contract(body, "agents")
    # The frontend reads `id` off a created conversation; it must remain present.
    assert isinstance(body["id"], str) and body["id"]


def test_agents_list_returns_empty_collection(client):
    resp = client.get("/api/agents/conversations")
    assert resp.status_code == 200
    assert resp.json() == []


def test_file_upload_returns_diagnostic_contract(client):
    resp = client.post("/api/files/upload")
    assert resp.status_code == 200
    body = resp.json()
    _assert_diagnostic_contract(body, "files")
    # Compat key preserved; no real storage is performed.
    assert isinstance(body["file_id"], str) and body["file_id"]


def test_diagnostic_reasons_are_distinct_and_documented(client):
    """Each stubbed subsystem must document a distinct reason."""
    fn = client.post("/api/functions/x/invoke", json={}).json()["reason"]
    ag = client.post("/api/agents/conversations", json={}).json()["reason"]
    fs = client.post("/api/files/upload").json()["reason"]
    assert len({fn, ag, fs}) == 3
