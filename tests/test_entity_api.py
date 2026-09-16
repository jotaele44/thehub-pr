"""Regression tests for the generic entity CRUD API (server/backend/main_core.py).

Covers the failure modes named in docs/handoff-audit/upgrade-audit/UPGRADE_AUDIT.md:
BUG-2 (duplicate id must 409, not 500 — already fixed on this HEAD, guarded here
against regression), BUG-3 (malformed/wrong-shape JSON bodies must 400, not 500),
and BUG-6 (an out-of-range `limit` must be rejected/clamped, not silently produce
a wrong answer).
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

import server.backend.main as backend_main  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(backend_main, "DB_PATH", tmp_path / "hub.db")
    monkeypatch.setattr(backend_main, "_WRITE_TOKEN", "entity-test-token")
    with TestClient(backend_main.app) as test_client:
        yield test_client


def auth():
    return {"Authorization": "Bearer entity-test-token"}


# ── BUG-2: duplicate id ──────────────────────────────────────────────────────

def test_duplicate_create_returns_409_not_500(client):
    payload = {"id": "DUP-TEST-001", "name": "first"}
    first = client.post("/api/entities/TestThing", json=payload, headers=auth())
    assert first.status_code == 200

    second = client.post("/api/entities/TestThing", json=payload, headers=auth())
    assert second.status_code == 409
    assert "DUP-TEST-001" in second.json()["detail"]


# ── BUG-3: malformed / wrong-shape JSON bodies ───────────────────────────────

def test_malformed_json_body_returns_400_not_500(client):
    response = client.post(
        "/api/entities/TestThing",
        content=b"{not valid json",
        headers={**auth(), "content-type": "application/json"},
    )
    assert response.status_code == 400


def test_non_object_json_body_returns_400(client):
    response = client.post("/api/entities/TestThing", json=["not", "an", "object"], headers=auth())
    assert response.status_code == 400


def test_update_rejects_non_object_patch(client):
    client.post("/api/entities/TestThing", json={"id": "row-1"}, headers=auth())
    response = client.patch(
        "/api/entities/TestThing/row-1", json="not an object", headers=auth()
    )
    assert response.status_code == 400


def test_bulk_create_rejects_non_dict_items(client):
    response = client.post(
        "/api/entities/TestThing/bulk", json={"items": ["nope"]}, headers=auth()
    )
    assert response.status_code == 400


def test_bulk_create_rejects_non_list_items(client):
    response = client.post(
        "/api/entities/TestThing/bulk", json={"items": "nope"}, headers=auth()
    )
    assert response.status_code == 400


def test_filter_rejects_non_dict_filters(client):
    response = client.post("/api/entities/TestThing/filter", json={"filters": ["nope"]})
    assert response.status_code == 400


def test_notifications_ack_rejects_non_object_body(client):
    response = client.post(
        "/api/notifications/ack", json=["nope"], headers=auth()
    )
    assert response.status_code == 400


# ── BUG-6: out-of-range `limit` ──────────────────────────────────────────────

def test_list_entities_rejects_out_of_range_limit(client):
    assert client.get("/api/entities/TestThing", params={"limit": 0}).status_code == 422
    assert client.get("/api/entities/TestThing", params={"limit": 5000}).status_code == 422


def test_filter_negative_limit_no_longer_silently_short_circuits_to_one(client):
    for i in range(3):
        client.post("/api/entities/TestThing", json={"id": f"row-{i}"}, headers=auth())

    response = client.post("/api/entities/TestThing/filter", json={"filters": {}, "limit": -1})
    assert response.status_code == 200
    # Clamped up to the minimum (1) rather than the old bug, where a negative
    # limit made `len(results) >= limit` true after the very first match for
    # an unrelated reason (any non-empty count is ">= a negative number").
    assert len(response.json()) == 1


def test_filter_oversized_limit_is_clamped_not_unbounded(client):
    for i in range(5):
        client.post("/api/entities/TestThing", json={"id": f"row-{i}"}, headers=auth())

    response = client.post(
        "/api/entities/TestThing/filter", json={"filters": {}, "limit": 10_000_000}
    )
    assert response.status_code == 200
    assert len(response.json()) == 5  # bounded by the actual row count, not the huge prefetch
