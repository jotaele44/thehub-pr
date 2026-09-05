"""Validate a producer's federation.json against repo_federation_manifest_v1."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple

import jsonschema

from ._schemas import load_schema


_FEDERATION_REPOS = (
    "thehub-pr",
    "moneysweep-pr",
    "spiderweb-pr",
    "aguayluz-pr",
    "skywatcher-pr",
    "centinelas-pr",
    "ovnis-pr",
)
_SETUP_COMMANDS = ("setup", "runtime_setup", "setup_test")


def _fmt(error: jsonschema.ValidationError) -> str:
    loc = "/".join(str(p) for p in error.path) or "<root>"
    return f"{loc}: {error.message}"


def _setup_isolation_errors(manifest: dict) -> List[str]:
    """Reject dependency setup commands that rely on sibling repo paths.

    Immutable package downloads remain valid; this guard is specifically about
    parent-workspace coupling that lets one Federation checkout block another.
    The same rule applies to the backward-compatible audit setup, the smaller
    runtime profile, and an optional test overlay.
    """
    commands = manifest.get("hub_callable_commands")
    if not isinstance(commands, dict):
        return []

    errors: List[str] = []
    for command_name in _SETUP_COMMANDS:
        command = commands.get(command_name)
        if not isinstance(command, str):
            continue
        for repo in _FEDERATION_REPOS:
            token = f"../{repo}"
            if token in command:
                errors.append(
                    f"hub_callable_commands/{command_name}: sibling repository path "
                    f"{token!r} is forbidden; use an immutable package, artifact, "
                    "schema, or explicit service contract instead"
                )
    return errors


def validate_repo_manifest(manifest: dict) -> List[str]:
    """Return a list of human-readable validation errors ([] == valid)."""
    schema = load_schema("repo_federation_manifest.schema.json")
    validator = jsonschema.Draft7Validator(schema)
    errors = [_fmt(e) for e in sorted(validator.iter_errors(manifest), key=str)]
    errors.extend(_setup_isolation_errors(manifest))
    return errors


def load_and_validate_manifest(path) -> Tuple[dict, List[str]]:
    data = json.loads(Path(path).read_text())
    return data, validate_repo_manifest(data)
