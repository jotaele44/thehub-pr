"""Loads and validates a repo's ``.federation/doctor-checks.json`` manifest.

This is the structured replacement for the free-text external-dependency
prose that already lives in each producer's ``federation.json``
(``source_truth.runtime_required_keys``, ``waf_blocked_sources``,
``federation_readiness_gate.blocking_conditions``) -- readable by a human,
but not something a tool can act on. A doctor-checks manifest turns each of
those into a structured, explicitly-classed entry (see
``types.DiagnosabilityClass``) that the engine can run deterministically.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .types import DiagnosabilityClass

SCHEMA_VERSION = "prii.doctor-checks/v1"


class ManifestError(Exception):
    """Raised when a doctor-checks manifest is missing, malformed, or fails schema validation."""


@dataclass
class CheckSpec:
    id: str
    diagnosability_class: DiagnosabilityClass
    check: dict[str, Any]
    description: str = ""
    category: str = ""
    severity_if_absent: str = "advisory"  # "blocking" | "advisory"
    operator_action: str = ""
    manifest_cross_check: str = ""
    last_known_state: dict[str, Any] = field(default_factory=dict)


@dataclass
class DoctorManifest:
    repository: str
    validation_entrypoint: str | None
    checks: list[CheckSpec]


def _schema_path() -> Path:
    return Path(__file__).resolve().parent / "schemas" / "doctor-checks.schema.json"


def _load_schema() -> dict[str, Any]:
    return json.loads(_schema_path().read_text(encoding="utf-8"))


def load(manifest_path: Path) -> DoctorManifest:
    """Load and validate a ``.federation/doctor-checks.json`` file.

    Raises ``ManifestError`` on anything wrong with the manifest itself --
    missing file, invalid JSON, schema mismatch, an unknown
    ``diagnosability_class``. This module never silently returns partial
    data; a caller that wants a softer failure (matching the federation's
    established "WARN, never fake-PASS" posture for a check that cannot run
    -- see spiderweb-pr's ``tools/pr_geodata_integrity_audit.py``) makes
    that choice at the call site. ``engine.run`` does exactly that: a
    missing manifest is a normal, silent "nothing declared yet" state, not
    an error.
    """
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestError(f"no doctor manifest at {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"{manifest_path}: invalid JSON ({exc})") from exc

    try:
        import jsonschema

        jsonschema.validate(raw, _load_schema())
    except ImportError:
        pass  # jsonschema is optional at runtime; CI enforces the schema separately.
    except Exception as exc:  # noqa: BLE001 - jsonschema raises several exception types
        raise ManifestError(f"{manifest_path}: schema validation failed: {exc}") from exc

    if raw.get("schema_version") != SCHEMA_VERSION:
        raise ManifestError(
            f"{manifest_path}: unsupported schema_version {raw.get('schema_version')!r}, "
            f"expected {SCHEMA_VERSION!r}"
        )

    checks: list[CheckSpec] = []
    for entry in raw.get("checks", []):
        try:
            diagnosability_class = DiagnosabilityClass(entry["diagnosability_class"])
        except (KeyError, ValueError) as exc:
            raise ManifestError(
                f"{manifest_path}: check {entry.get('id', '?')!r} has an invalid "
                f"diagnosability_class: {exc}"
            ) from exc
        checks.append(
            CheckSpec(
                id=entry["id"],
                diagnosability_class=diagnosability_class,
                check=entry.get("check", {"type": "manual"}),
                description=entry.get("description", ""),
                category=entry.get("category", ""),
                severity_if_absent=entry.get("severity_if_absent", "advisory"),
                operator_action=entry.get("operator_action", ""),
                manifest_cross_check=entry.get("manifest_cross_check", ""),
                last_known_state=entry.get("last_known_state", {}),
            )
        )
    return DoctorManifest(
        repository=raw.get("repository", ""),
        validation_entrypoint=raw.get("validation_entrypoint"),
        checks=checks,
    )
