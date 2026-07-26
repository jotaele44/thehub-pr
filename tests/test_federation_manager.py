from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from jsonschema import ValidationError
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
