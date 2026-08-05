#!/usr/bin/env python3
"""Validate TheHub MCP project manifests against the capability registry."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft7Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "schemas" / "federation" / "project_mcp_manifest.schema.json"
REGISTRY_PATH = REPO_ROOT / "mcp" / "registry" / "capability_registry.yaml"
MANIFESTS_DIR = REPO_ROOT / "mcp" / "manifests"

EXPECTED_PROJECTS = {
    "skywatcher",
    "ovnis",
    "spiderweb",
    "centinelas",
    "moneysweep",
    "aguayluz",
}

FORBIDDEN_TERMS = [
    "api_key:",
    "token:",
    "password:",
    "secret:",
    "confirmed anomaly",
    "confirmed uap",
    "confirmed uso",
]


def scan_forbidden_terms(text: str, source: str) -> list[str]:
    lowered = text.lower()
    return [
        f"{source}: forbidden term found: {term!r}"
        for term in FORBIDDEN_TERMS
        if term in lowered
    ]


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate() -> list[str]:
    errors: list[str] = []

    if not REGISTRY_PATH.is_file():
        return [f"registry file not found: {REGISTRY_PATH}"]
    if not MANIFESTS_DIR.is_dir():
        return [f"manifests directory not found: {MANIFESTS_DIR}"]
    if not SCHEMA_PATH.is_file():
        return [f"schema file not found: {SCHEMA_PATH}"]

    registry_text = REGISTRY_PATH.read_text(encoding="utf-8")
    errors.extend(scan_forbidden_terms(registry_text, str(REGISTRY_PATH)))

    registry = load_yaml(REGISTRY_PATH)
    adapter_status_values = set(registry.get("adapter_status_values", []))
    capabilities = registry.get("capabilities", {})
    project_local_capabilities = registry.get("project_local_capabilities", {})
    global_capability_names = set(capabilities.keys())

    for name, spec in capabilities.items():
        version_pin = spec.get("version_pin")
        if not version_pin:
            errors.append(f"registry capability {name!r} is missing version_pin")
        status = spec.get("status")
        if status not in adapter_status_values:
            errors.append(
                f"registry capability {name!r} has invalid status {status!r}"
            )
        # pending-evaluation is reserved for pilot/conditional adapters; an
        # active capability must carry a concrete pin.
        if version_pin == "pending-evaluation" and status == "active":
            errors.append(
                f"registry capability {name!r} is active but version_pin is "
                f"pending-evaluation"
            )

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft7Validator(schema)

    manifest_paths = sorted(MANIFESTS_DIR.glob("*.mcp.yaml"))
    found_projects = {p.name.removesuffix(".mcp.yaml") for p in manifest_paths}
    missing_projects = EXPECTED_PROJECTS - found_projects
    if missing_projects:
        errors.append(
            f"missing manifest(s) for project(s): {sorted(missing_projects)}"
        )
    unexpected_projects = found_projects - EXPECTED_PROJECTS
    if unexpected_projects:
        errors.append(
            f"unexpected manifest file(s) for: {sorted(unexpected_projects)}"
        )

    validated_count = 0
    for manifest_path in manifest_paths:
        manifest_text = manifest_path.read_text(encoding="utf-8")
        errors.extend(scan_forbidden_terms(manifest_text, str(manifest_path)))

        manifest = load_yaml(manifest_path)
        schema_errors = sorted(validator.iter_errors(manifest), key=str)
        if schema_errors:
            for e in schema_errors:
                errors.append(f"{manifest_path}: schema error: {e.message}")
            continue

        if manifest["write_policy"]["default"] != "read_only":
            errors.append(
                f"{manifest_path}: write_policy.default must be read_only, "
                f"got {manifest['write_policy']['default']!r}"
            )

        project = manifest["project"]
        expected_name = f"{project}.mcp.yaml"
        if manifest_path.name != expected_name:
            errors.append(
                f"{manifest_path}: declares project {project!r} but filename "
                f"is not {expected_name!r}"
            )

        allowed_local = set(project_local_capabilities.get(project, []))
        declared = list(manifest.get("inherits", [])) + list(
            manifest.get("capabilities", [])
        )
        for cap in declared:
            if cap not in global_capability_names and cap not in allowed_local:
                errors.append(
                    f"{manifest_path}: capability {cap!r} is neither a global "
                    f"registry capability nor an allowed project-local "
                    f"capability for {project!r}"
                )

        validated_count += 1

    if not errors:
        print(f"Validated {validated_count} MCP manifest(s).")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
