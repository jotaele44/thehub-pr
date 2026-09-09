"""Regression tests for the generic entity CRUD API (server/backend/main_core.py).

Covers the failure modes named in docs/handoff-audit/upgrade-audit/UPGRADE_AUDIT.md:
BUG-2 (duplicate id must 409, not 500 — already fixed on this HEAD, guarded here
against regression), BUG-3 (malformed/wrong-shape JSON bodies must 400, not 500),
and BUG-6 (an out-of-range `limit` must be rejected/clamped, not silently produce
a wrong answer).
"""
from __future__ import annotations

import pytest
import json
from contextlib import closing

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


@pytest.mark.parametrize("entity_id", [None, "", "   ", 0, 42, False, [], {}, ["id"]])
@pytest.mark.parametrize("bulk", [False, True])
def test_invalid_ids_fail_before_writing(client, entity_id, bulk):
    item = {"id": entity_id, "name": "invalid"}
    path = "/api/entities/BadId" + ("/bulk" if bulk else "")
    payload = {"items": [{"id": "valid"}, item]} if bulk else item
    response = client.post(path, json=payload, headers=auth())
    assert response.status_code == 400
    assert client.get("/api/entities/BadId").json() == []


def test_raw_id_round_trips_and_cannot_be_reassigned(client):
    raw_id = " ID-á "
    response = client.post("/api/entities/TestThing", json={"id": raw_id}, headers=auth())
    assert response.json()["id"] == raw_id
    response = client.patch(
        f"/api/entities/TestThing/{raw_id}", json={"id": "replacement"}, headers=auth()
    )
    assert response.status_code == 400
    assert client.get(f"/api/entities/TestThing/{raw_id}").json()["id"] == raw_id
    response = client.patch(
        f"/api/entities/TestThing/{raw_id}", json={"id": raw_id, "name": "updated"}, headers=auth()
    )
    assert response.status_code == 200
    assert response.json()["id"] == raw_id


def test_bulk_duplicate_ids_fail_atomically(client):
    response = client.post(
        "/api/entities/TestThing/bulk",
        json={"items": [{"id": "same", "name": "first"}, {"id": "same", "name": "second"}]},
        headers=auth(),
    )
    assert response.status_code == 400
    assert client.get("/api/entities/TestThing").json() == []


@pytest.mark.parametrize("sort", ["created_date", "-created_date"])
def test_filter_finds_matches_beyond_old_prefetch_cap(client, sort):
    with closing(backend_main._conn()) as connection:
        connection.executemany(
            "INSERT INTO entities VALUES (?, ?, ?, ?)",
            [("DeepMatch", f"row-{i:05}", json.dumps({"id": f"row-{i:05}", "match": i == 5500}), f"{i:05}")
             for i in range(11001)],
        )
        connection.commit()
    response = client.post(
        "/api/entities/DeepMatch/filter", json={"filters": {"match": True}, "limit": 1, "sort": sort}
    )
    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == ["row-05500"]


def test_invalid_utf8_returns_400(client):
    response = client.post("/api/entities/TestThing", content=b'\xff', headers=auth())
    assert response.status_code == 400


@pytest.mark.parametrize("body", [b"[]", b"null", b'"text"', b'{invalid', b'\xff'])
def test_sign_generation_rejects_invalid_optional_body(client, body):
    response = client.post("/api/project-signs/generate", content=body, headers=auth())
    assert response.status_code == 400


def test_sign_generation_accepts_omitted_body(client):
    assert client.post("/api/project-signs/generate", headers=auth()).status_code == 200


@pytest.mark.parametrize("value", ["false", 1, [], None])
def test_sign_generation_requires_boolean_write_flag(client, value):
    response = client.post("/api/project-signs/generate", json={"write": value}, headers=auth())
    assert response.status_code == 400


def test_bulk_upsert_existing_record_preserves_supported_behavior(client):
    client.post("/api/entities/TestThing", json={"id": "existing", "name": "old"}, headers=auth())
    response = client.post(
        "/api/entities/TestThing/bulk",
        json={"items": [{"id": "existing", "name": "new"}, {"name": "generated"}]}, headers=auth(),
    )
    assert response.status_code == 200
    assert len({item["id"] for item in response.json()}) == 2
    assert client.get("/api/entities/TestThing/existing").json()["name"] == "new"


def test_generated_and_legacy_field_ids_remain_supported(client):
    created = client.post("/api/entities/TestThing", json={"name": "generated"}, headers=auth())
    assert isinstance(created.json()["id"], str)
    assert client.get(f'/api/entities/TestThing/{created.json()["id"]}').status_code == 200
    legacy = client.post("/api/entities/Programs", json={"program_id": " raw-á "}, headers=auth())
    assert legacy.json()["id"] == " raw-á "


@pytest.mark.parametrize("value", [b"NaN", b"Infinity", b"-Infinity", b"1e309"])
def test_nonfinite_json_is_rejected_without_persisting(client, value):
    response = client.post(
        "/api/entities/Nonfinite", content=b'{"nested": {"value": ' + value + b'}}', headers=auth()
    )
    assert response.status_code == 400
    assert client.get("/api/entities/Nonfinite").json() == []


@pytest.mark.parametrize("value", [False, 0, [], {}, 2])
def test_filter_rejects_non_string_sort_even_when_falsy(client, value):
    response = client.post("/api/entities/TestThing/filter", json={"sort": value})
    assert response.status_code == 400
