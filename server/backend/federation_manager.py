"""Read-only Federation Manager foundation.

This module intentionally contains no download, install, update, uninstall,
data-delete, process-launch, or shell-execution capability.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
import secrets
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

APP_IDS = (
    "thehub",
    "ovnis",
    "centinelas",
    "skywatcher",
    "aguayluz",
    "spiderweb",
    "moneysweep",
)

APP_CATALOG: tuple[dict[str, Any], ...] = (
    {"appId": "thehub", "displayName": "TheHub", "profile": "core", "iconId": "thehub"},
    {"appId": "ovnis", "displayName": "OVNIS", "profile": "one_click", "iconId": "ovnis"},
    {"appId": "centinelas", "displayName": "Centinelas", "profile": "guided", "iconId": "centinelas"},
    {"appId": "skywatcher", "displayName": "Skywatcher", "profile": "guided", "iconId": "skywatcher"},
    {"appId": "aguayluz", "displayName": "AguaYLuz", "profile": "guided", "iconId": "aguayluz"},
    {"appId": "spiderweb", "displayName": "Spiderweb", "profile": "one_click_basic", "iconId": "spiderweb"},
    {"appId": "moneysweep", "displayName": "MoneySweep", "profile": "multistage", "iconId": "moneysweep"},
)

READINESS_DIMENSIONS = ("install", "configuration", "data", "federation", "production")
SECRET_KEY_PATTERN = ("secret", "token", "password", "api_key", "authorization", "credential")
FORBIDDEN_MANIFEST_FIELDS = (
    "command",
    "commands",
    "shell",
    "script",
    "executable",
    "hub_callable_commands",
)


class ManifestSecurityError(ValueError):
    """Raised when declarative release metadata contains executable material."""


def _walk_keys(value: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            keys.append(str(key).lower())
            keys.extend(_walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.extend(_walk_keys(child))
    return keys


def validate_release_manifest(manifest: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    """Validate structure and reject every executable/arbitrary-command field."""
    Draft202012Validator(schema).validate(manifest)
    present = set(_walk_keys(manifest))
    forbidden = sorted(set(FORBIDDEN_MANIFEST_FIELDS) & present)
    if forbidden:
        raise ManifestSecurityError(f"executable manifest fields are forbidden: {forbidden}")


@dataclass(frozen=True)
class Readiness:
    install: str
    configuration: str
    data: str
    federation: str
    production: str


@dataclass(frozen=True)
class AppState:
    app_id: str
    display_name: str
    profile: str
    icon_id: str
    lifecycle: str
    readiness: Readiness
    installed_version: str | None
    available_version: str | None
    available_actions: tuple[str, ...]
    technical_details: Mapping[str, Any]

    def public_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["appId"] = value.pop("app_id")
        value["displayName"] = value.pop("display_name")
        value["iconId"] = value.pop("icon_id")
        value["installedVersion"] = value.pop("installed_version")
        value["availableVersion"] = value.pop("available_version")
        value["availableActions"] = value.pop("available_actions")
        value["technicalDetails"] = redact_technical_details(value.pop("technical_details"))
        return value


ALLOWED_TRANSITIONS: Mapping[str, Mapping[str, str]] = {
    "available": {"install": "installing", "connect": "installed"},
    "installing": {"verified": "installed", "failed": "available"},
    "installed": {"setup": "configuring", "validate_ready": "ready", "validate_limited": "limited"},
    "configuring": {"required_ready": "ready", "optional_missing": "limited"},
    "ready": {"health_failed": "degraded", "update": "updating"},
    "limited": {"required_ready": "ready", "update": "updating"},
    "updating": {"verified": "ready", "rollback_succeeded": "ready", "rollback_failed": "degraded"},
    "degraded": {"repair": "repairing"},
    "repairing": {"verified": "ready", "failed": "degraded"},
}


def transition(current: str, event: str) -> str:
    try:
        return ALLOWED_TRANSITIONS[current][event]
    except KeyError as exc:
        raise ValueError(f"invalid app transition: {current} + {event}") from exc


def redact_technical_details(value: Any) -> Any:
    """Recursively redact secret-bearing keys while preserving diagnostics."""
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, child in value.items():
            normalized = str(key).lower()
            result[str(key)] = (
                "[REDACTED]"
                if any(marker in normalized for marker in SECRET_KEY_PATTERN)
                else redact_technical_details(child)
            )
        return result
    if isinstance(value, list):
        return [redact_technical_details(item) for item in value]
    return value


@dataclass(frozen=True)
class OSPaths:
    apps: Path
    config: Path
    data: Path
    logs: Path


def resolve_os_paths(
    system: str | None = None, env: Mapping[str, str] | None = None, home: Path | None = None
) -> OSPaths:
    system = (system or platform.system()).lower()
    env = env or os.environ
    home = home or Path.home()
    if system == "darwin":
        base = home / "Library" / "Application Support" / "PRII"
        return OSPaths(base / "apps", base / "config", base / "data", home / "Library" / "Logs" / "PRII")
    if system == "windows":
        local = Path(env.get("LOCALAPPDATA", home / "AppData" / "Local")) / "PRII"
        roaming = Path(env.get("APPDATA", home / "AppData" / "Roaming")) / "PRII"
        return OSPaths(local / "apps", roaming / "config", local / "data", local / "logs")
    data = Path(env.get("XDG_DATA_HOME", home / ".local" / "share")) / "prii"
    config = Path(env.get("XDG_CONFIG_HOME", home / ".config")) / "prii"
    state = Path(env.get("XDG_STATE_HOME", home / ".local" / "state")) / "prii"
    return OSPaths(data / "apps", config, data / "data", state / "logs")


class SecretProvider(ABC):
    """Interface only; platform keychain implementations land in a later phase."""

    @abstractmethod
    def set(self, app_id: str, secret_id: str, value: str) -> None: ...

    @abstractmethod
    def exists(self, app_id: str, secret_id: str) -> bool: ...

    @abstractmethod
    def delete(self, app_id: str, secret_id: str) -> None: ...


class UnavailableSecretProvider(SecretProvider):
    def set(self, app_id: str, secret_id: str, value: str) -> None:
        raise RuntimeError("OS credential provider is not configured")

    def exists(self, app_id: str, secret_id: str) -> bool:
        return False

    def delete(self, app_id: str, secret_id: str) -> None:
        raise RuntimeError("OS credential provider is not configured")


class SessionManager:
    """In-memory, short-lived, origin-bound opaque sessions."""

    def __init__(self, bootstrap_nonce: str, allowed_origins: set[str], ttl_seconds: int = 300):
        self._nonce_digest = hashlib.sha256(bootstrap_nonce.encode()).digest()
        self.allowed_origins = frozenset(allowed_origins)
        self.ttl_seconds = ttl_seconds
        self._sessions: dict[str, tuple[float, str]] = {}

    def exchange(self, nonce: str, origin: str, now: float | None = None) -> tuple[str, float]:
        if origin not in self.allowed_origins:
            raise PermissionError("origin is not allowed")
        supplied = hashlib.sha256(nonce.encode()).digest()
        if not hmac.compare_digest(supplied, self._nonce_digest):
            raise PermissionError("invalid bootstrap nonce")
        now = time.time() if now is None else now
        token = secrets.token_urlsafe(32)
        expires = now + self.ttl_seconds
        self._sessions[token] = (expires, origin)
        return token, expires

    def validate(self, token: str, origin: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        record = self._sessions.get(token)
        if not record:
            return False
        expires, expected_origin = record
        if now >= expires or origin != expected_origin or origin not in self.allowed_origins:
            self._sessions.pop(token, None)
            return False
        return True


def read_only_inventory() -> list[dict[str, Any]]:
    paths = resolve_os_paths()
    result = []
    for app in APP_CATALOG:
        is_core = app["appId"] == "thehub"
        state = AppState(
            app_id=app["appId"],
            display_name=app["displayName"],
            profile=app["profile"],
            icon_id=app["iconId"],
            lifecycle="ready" if is_core else "available",
            readiness=Readiness(
                install="installed" if is_core else "absent",
                configuration="not_required" if is_core else "incomplete",
                data="partial" if is_core else "empty",
                federation="compatible" if is_core else "unknown",
                production="not_assessed",
            ),
            installed_version="0.1.0" if is_core else None,
            available_version=None,
            available_actions=("open", "validate") if is_core else (),
            technical_details={
                "profile": app["profile"],
                "paths": {"apps": str(paths.apps), "data": str(paths.data)},
                "secureStoreAvailable": False,
            },
        )
        result.append(state.public_dict())
    return result


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
