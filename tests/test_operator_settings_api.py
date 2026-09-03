from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

import server.backend.main as backend_main  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(backend_main, "DB_PATH", tmp_path / "hub.db")
    monkeypatch.setattr(backend_main, "_WRITE_TOKEN", "settings-token")
    with TestClient(backend_main.app) as test_client:
        yield test_client


def auth(token="settings-token"):
    return {"Authorization": f"Bearer {token}"}


def test_preferences_require_write_token_and_round_trip_normalized_data(client):
    payload = {
        "subscriber": " operator ",
        "prefs": {
            "all": {"channels": ["push", "push"], "timing": "asap"},
            "water": {"channels": ["sms"], "timing": "brief"},
        },
        "targets": {
            "push": " https://push.example/subscription ",
            "sms": " +17875550123 ",
        },
    }
    assert client.put("/api/notifications/preferences", json=payload).status_code == 401
    assert client.put(
        "/api/notifications/preferences", json=payload, headers=auth("wrong")
    ).status_code == 401

    response = client.put(
        "/api/notifications/preferences", json=payload, headers=auth()
    )
    assert response.status_code == 200
    assert response.json() == {
        "subscriber": "operator",
        "prefs": {
            "all": {"channels": ["push"], "timing": "asap"},
            "water": {"channels": ["sms"], "timing": "brief"},
        },
        "targets": {
            "push": "https://push.example/subscription",
            "sms": "+17875550123",
        },
    }
    stored = client.get(
        "/api/notifications/preferences", params={"subscriber": "operator"}
    ).json()
    assert stored["prefs"] == response.json()["prefs"]
    assert stored["targets"] == response.json()["targets"]


@pytest.mark.parametrize(
    "payload, detail",
    [
        ({"prefs": []}, "prefs must be an object"),
        (
            {"prefs": {"all": {"channels": ["email"], "timing": "asap"}}},
            "channels for all",
        ),
        (
            {"prefs": {"unknown": {"channels": [], "timing": "asap"}}},
            "unknown notification domain",
        ),
        (
            {
                "prefs": {"all": {"channels": ["push"], "timing": "asap"}},
                "targets": {"push": "javascript:alert(1)"},
            },
            "absolute HTTP(S) URL",
        ),
        (
            {
                "prefs": {"all": {"channels": ["sms"], "timing": "asap"}},
                "targets": {"sms": "787-555-0123"},
            },
            "E.164",
        ),
    ],
)
def test_preferences_reject_malformed_input(client, payload, detail):
    response = client.put(
        "/api/notifications/preferences", json=payload, headers=auth()
    )
    assert response.status_code == 422
    assert detail in response.json()["detail"]


def test_preferences_drop_targets_for_disabled_channels(client):
    response = client.put(
        "/api/notifications/preferences",
        headers=auth(),
        json={
            "prefs": {"all": {"channels": [], "timing": "asap"}},
            "targets": {"push": "https://push.example/subscription"},
        },
    )
    assert response.status_code == 200
    assert response.json()["targets"] == {}


def test_upload_connector_and_mcp_contracts_are_real_http_routes(client):
    upload = client.post("/api/files/upload")
    assert upload.status_code == 200
    assert upload.json()["implemented"] is False
    assert upload.json()["file_id"]

    connector = client.get("/api/connectors/github/connection")
    assert connector.status_code == 200
    assert connector.json() == {"status": "not_connected", "name": "github"}

    capabilities = client.get("/mcp/capabilities")
    assert capabilities.status_code == 200


def test_duplicate_entity_id_returns_conflict(client):
    payload = {"id": "duplicate", "name": "First"}
    assert client.post("/api/entities/Widgets", json=payload, headers=auth()).status_code == 200
    response = client.post("/api/entities/Widgets", json=payload, headers=auth())
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]
