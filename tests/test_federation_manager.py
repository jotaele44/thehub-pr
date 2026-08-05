from __future__ import annotations

import json
import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException
from jsonschema import ValidationError
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from server.backend.federation_manager import (
    APP_IDS,
    ManifestSecurityError,
    SessionManager,
    UnavailableSecretProvider,
    read_only_inventory,
    redact_technical_details,
    resolve_os_paths,
    transition,
    validate_release_manifest,
)
from server.backend.federation_manager_api import _require_loopback
from server.backend import federation_manager_api

ROOT = Path(__file__).parents[1]
SCHEMA = json.loads(
    (ROOT / "schemas" / "federation_manager_release_manifest.schema.json").read_text()
)


def valid_manifest():
    apps = []
    names = ("TheHub", "OVNIS", "Centinelas", "Skywatcher", "AguaYLuz", "Spiderweb", "MoneySweep")
    for app_id, name in zip(APP_IDS, names):
        apps.append(
            {
                "appId": app_id,
                "displayName": name,
                "version": "0.3.0",
                "sourceCommit": "a" * 40,
                "channel": "developer",
                "artifacts": [
                    {
                        "os": "macos",
                        "arch": "arm64",
                        "format": "dmg",
                        "url": "https://example.invalid/app.dmg",
                        "size": 1,
                        "sha256": "b" * 64,
                        "signature": {"algorithm": "ed25519", "value": "signed"},
                    }
                ],
                "compatibility": {"manager": ">=0.3", "federationContract": "v1"},
            }
        )
    return {
        "schemaVersion": "prii-release-catalog-v1",
        "catalogVersion": 1,
        "generatedAt": "2026-07-26T00:00:00Z",
        "signingKeyId": "developer-key",
        "apps": apps,
        "signature": {"algorithm": "ed25519", "value": "x" * 32},
    }


def test_release_schema_positive_and_tamper_negative():
    validate_release_manifest(valid_manifest(), SCHEMA)
    tampered = valid_manifest()
    tampered["apps"][0]["sourceCommit"] = "not-a-sha"
    with pytest.raises(ValidationError):
        validate_release_manifest(tampered, SCHEMA)


def test_release_schema_rejects_duplicate_apps():
    manifest = valid_manifest()
    manifest["apps"] = [manifest["apps"][0]] * 7
    with pytest.raises(ValidationError):
        validate_release_manifest(manifest, SCHEMA)


def test_release_schema_rejects_identity_display_name_mismatch():
    manifest = valid_manifest()
    manifest["apps"][0]["displayName"] = "MoneySweep"
    with pytest.raises(ValidationError):
        validate_release_manifest(manifest, SCHEMA)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("generatedAt",), "not-a-date"),
        (("apps", 0, "artifacts", 0, "url"), "https://"),
    ],
)
def test_release_schema_enforces_formats(path, value):
    manifest = valid_manifest()
    target = manifest
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        validate_release_manifest(manifest, SCHEMA)


@pytest.mark.parametrize("field", ["command", "shell", "script", "executable", "hub_callable_commands"])
def test_arbitrary_command_fields_are_rejected_at_any_depth(field):
    schema = json.loads(json.dumps(SCHEMA))
    schema["$defs"]["artifact"]["additionalProperties"] = True
    manifest = valid_manifest()
    manifest["apps"][0]["artifacts"][0][field] = "echo forbidden"
    with pytest.raises(ManifestSecurityError):
        validate_release_manifest(manifest, schema)


def test_state_transitions_and_invalid_transition():
    assert transition("available", "install") == "installing"
    assert transition("configuring", "optional_missing") == "limited"
    assert transition("updating", "rollback_succeeded") == "ready"
    with pytest.raises(ValueError):
        transition("available", "delete_data")


def test_session_origin_expiry_and_nonce():
    manager = SessionManager("n" * 32, {"http://localhost:5173"}, ttl_seconds=5)
    with pytest.raises(PermissionError):
        manager.exchange("n" * 32, "https://evil.invalid", now=10)
    with pytest.raises(PermissionError):
        manager.exchange("x" * 32, "http://localhost:5173", now=10)
    token, _ = manager.exchange("n" * 32, "http://localhost:5173", now=10)
    assert manager.validate(token, "http://localhost:5173", now=14)
    assert not manager.validate(token, "http://localhost:5173", now=15)


def test_non_loopback_requests_are_rejected():
    loopback = Request({"type": "http", "client": ("127.0.0.1", 1234), "headers": []})
    _require_loopback(loopback)
    remote = Request({"type": "http", "client": ("192.0.2.10", 1234), "headers": []})
    with pytest.raises(HTTPException, match="loopback only") as exc:
        _require_loopback(remote)
    assert exc.value.status_code == 403


def test_fastapi_endpoint_annotations_are_python_39_compatible():
    for endpoint in (federation_manager_api.list_apps, federation_manager_api.get_app):
        assert " | " not in str(inspect.signature(endpoint))


@pytest.fixture
def manager_client(monkeypatch):
    nonce = "n" * 32
    manager = SessionManager(nonce, {"http://localhost:5173"}, ttl_seconds=5)
    monkeypatch.setattr(federation_manager_api, "_bootstrap_nonce", nonce)
    monkeypatch.setattr(federation_manager_api, "sessions", manager)
    monkeypatch.setattr(federation_manager_api, "_require_loopback", lambda request: None)
    app = FastAPI()
    app.include_router(federation_manager_api.router)
    return TestClient(app), manager, nonce


def test_api_rejects_origin_and_missing_auth(manager_client):
    client, _, nonce = manager_client
    rejected = client.post(
        "/api/federation-manager/session",
        headers={"origin": "https://evil.invalid"},
        json={"nonce": nonce, "origin": "https://evil.invalid"},
    )
    assert rejected.status_code == 403
    missing = client.get(
        "/api/federation-manager/apps",
        headers={"origin": "http://localhost:5173"},
    )
    assert missing.status_code == 401


def test_api_accepts_native_session_and_rejects_expired_token(manager_client):
    client, manager, nonce = manager_client
    session = client.post(
        "/api/federation-manager/session",
        headers={"origin": "http://localhost:5173"},
        json={"nonce": nonce, "origin": "http://localhost:5173"},
    )
    assert session.status_code == 200
    token = session.json()["token"]
    inventory = client.get(
        "/api/federation-manager/apps",
        headers={
            "origin": "http://localhost:5173",
            "authorization": f"Bearer {token}",
        },
    )
    assert inventory.status_code == 200
    assert len(inventory.json()) == 7
    expired_token, _ = manager.exchange(nonce, "http://localhost:5173", now=0)
    expired = client.get(
        "/api/federation-manager/apps",
        headers={
            "origin": "http://localhost:5173",
            "authorization": f"Bearer {expired_token}",
        },
    )
    assert expired.status_code == 401


def test_secret_non_disclosure_and_interface_has_no_get():
    value = redact_technical_details(
        {"api_key": "visible-before-redaction", "nested": {"authorizationToken": "secret"}, "port": 8000}
    )
    assert value["api_key"] == "[REDACTED]"
    assert value["nested"]["authorizationToken"] == "[REDACTED]"
    assert value["port"] == 8000
    assert not hasattr(UnavailableSecretProvider(), "get")


def test_os_path_separation():
    paths = resolve_os_paths("linux", {}, Path("/users/operator"))
    assert paths.apps != paths.data
    assert paths.config != paths.logs
    assert "prii" in str(paths.apps)


def test_seven_apps_and_readiness_dimensions_are_independent():
    inventory = read_only_inventory()
    assert [item["appId"] for item in inventory] == list(APP_IDS)
    assert [item["displayName"] for item in inventory] == [
        "TheHub", "OVNIS", "Centinelas", "Skywatcher", "AguaYLuz", "Spiderweb", "MoneySweep"
    ]
    for item in inventory:
        assert set(item["readiness"]) == {
            "install", "configuration", "data", "federation", "production"
        }
        assert "credential" not in json.dumps(item["technicalDetails"]).lower()
