"""Federation readiness rollup for producer workspaces.

This module is intentionally filesystem-local. It does not clone, fetch, or run
producer commands; it summarizes what the Hub can validate from an existing
workspace checkout.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .manifest import load_and_validate_manifest
from .registry import Producer, Registry
from .validate import validate_package


@dataclass(frozen=True)
class ProducerReadiness:
    program_id: str
    repo: str
    role: str
    declared_status: str
    local_path: str
    checkout_present: bool
    manifest_path: str
    manifest_present: bool
    manifest_valid: bool
    package_path: str
    package_present: bool
    package_valid: bool
    live_execution_ready: bool
    callable_commands: List[str]
    last_package_timestamp: Optional[str]
    blocker_class: str
    errors: List[str]


def _producer_base(root: Path, producer: Producer) -> Path:
    if producer.local_path:
        return root / producer.local_path
    return root / producer.repo_name


def _blocker_class(
    *,
    checkout_present: bool,
    manifest_present: bool,
    manifest_valid: bool,
    package_present: bool,
    package_valid: bool,
    live_execution_ready: bool,
    declared_status: str,
) -> str:
    if not checkout_present:
        return "missing_checkout"
    if not manifest_present:
        return "missing_manifest"
    if not manifest_valid:
        return "invalid_manifest"
    if not package_present:
        return "missing_export_package"
    if not package_valid:
        return "invalid_export_package"
    if not live_execution_ready:
        return "declared_not_live"
    if declared_status in {"blocked", "diagnostic", "synthetic_only"}:
        return "declared_not_live"
    return "ready"


def _read_federation_json(manifest_path: Path) -> Dict[str, Any]:
    """Parse a producer's federation.json; return {} on any failure."""
    try:
        return json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def validate_federation(registry: Registry, root: str | Path = ".") -> Dict[str, Any]:
    """Return a Hub-level readiness summary for all registered producers."""
    root_path = Path(root)
    producers: List[ProducerReadiness] = []

    for producer in registry.producers:
        base = _producer_base(root_path, producer)
        manifest_path = base / producer.federation_manifest
        package_path = base / producer.export_path
        errors: List[str] = []

        checkout_present = base.exists()
        manifest_present = manifest_path.exists()
        manifest_valid = False
        live_execution_ready = False
        callable_commands: List[str] = []

        if manifest_present:
            _, manifest_errors = load_and_validate_manifest(manifest_path)
            if manifest_errors:
                errors.extend(f"manifest: {err}" for err in manifest_errors)
            else:
                manifest_valid = True

            fed_data = _read_federation_json(manifest_path)
            gate = fed_data.get("federation_readiness_gate", {})
            live_execution_ready = bool(gate.get("ready_for_hub_live_execution", False))
            callable_commands = sorted(fed_data.get("hub_callable_commands", {}).keys())

        package_present = package_path.exists()
        package_valid = False
        last_package_timestamp: Optional[str] = None

        if package_present:
            package_errors = validate_package(package_path)
            if package_errors:
                errors.extend(f"package: {err}" for err in package_errors[:50])
                if len(package_errors) > 50:
                    errors.append(f"package: ... and {len(package_errors) - 50} more")
            else:
                package_valid = True

            pkg_manifest_path = package_path / "manifest.json"
            if pkg_manifest_path.exists():
                try:
                    pkg_manifest = json.loads(pkg_manifest_path.read_text())
                    last_package_timestamp = pkg_manifest.get("created_at")
                except (OSError, json.JSONDecodeError):
                    pass

        blocker_class = _blocker_class(
            checkout_present=checkout_present,
            manifest_present=manifest_present,
            manifest_valid=manifest_valid,
            package_present=package_present,
            package_valid=package_valid,
            live_execution_ready=live_execution_ready,
            declared_status=producer.status,
        )
        producers.append(
            ProducerReadiness(
                program_id=producer.program_id,
                repo=producer.repo,
                role=producer.role,
                declared_status=producer.status,
                local_path=str(base),
                checkout_present=checkout_present,
                manifest_path=str(manifest_path),
                manifest_present=manifest_present,
                manifest_valid=manifest_valid,
                package_path=str(package_path),
                package_present=package_present,
                package_valid=package_valid,
                live_execution_ready=live_execution_ready,
                callable_commands=callable_commands,
                last_package_timestamp=last_package_timestamp,
                blocker_class=blocker_class,
                errors=errors,
            )
        )

    by_blocker: Dict[str, int] = {}
    for producer in producers:
        by_blocker[producer.blocker_class] = by_blocker.get(producer.blocker_class, 0) + 1

    return {
        "hub": registry.hub,
        "schema_version": registry.schema_version,
        "root": str(root_path),
        "producer_count": len(producers),
        "ready_count": by_blocker.get("ready", 0),
        "by_blocker": dict(sorted(by_blocker.items())),
        "producers": [asdict(producer) for producer in producers],
    }
