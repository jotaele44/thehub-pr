from fastapi.testclient import TestClient

from server.backend.main import app


def test_companion_capability_surface_is_read_only_and_bounded():
    with TestClient(app) as client:
        response = client.get("/api/admin-companion/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["default_effect"] == "DENY"
    assert body["workstation_manager_access"] is False
    forbidden = {"lockstep.override", "certification.issue", "deployment.promote", "secret.write"}
    assert forbidden.isdisjoint(body["capabilities"])


def test_unconfigured_entity_write_fails_closed(monkeypatch):
    import server.backend.main as backend
    monkeypatch.setattr(backend, "_WRITE_TOKEN", "")
    with TestClient(backend.app) as client:
        response = client.post("/api/entities/Programs", json={"id": "forbidden"})
    assert response.status_code == 503
