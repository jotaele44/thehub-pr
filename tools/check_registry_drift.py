#!/usr/bin/env python3
"""Detect drift between the MCP capability registry and project manifests.

A global capability's ``required_by`` list and the set of manifests that
declare it must agree. This checks both directions:

  * missing — a project is in a capability's ``required_by`` but its manifest
    does not declare that capability;
  * extra   — a manifest declares a global capability whose ``required_by``
    does not list that project.

Project-local capabilities (declared in a manifest but not present in the
registry ``capabilities`` map) are not governed by ``required_by`` and are
ignored. Standalone (PyYAML only, no ``hub`` import) so it runs anywhere the
other ``tools/validate_mcp_*.py`` scripts do.

Exit code 0 when clean, 1 on drift.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_REGISTRY = _REPO_ROOT / "mcp" / "registry" / "capability_registry.yaml"
_DEFAULT_MANIFESTS = _REPO_ROOT / "mcp" / "manifests"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def find_drift(registry_path: Path, manifests_dir: Path) -> List[str]:
    """Return a list of human-readable drift messages (empty = no drift)."""
    registry = _load(registry_path)
    capabilities: Dict[str, dict] = registry.get("capabilities", {}) or {}
    global_names = set(capabilities)

    # capability -> set(projects it is required_by)
    required_by: Dict[str, set] = {
        name: set(spec.get("required_by", []) or [])
        for name, spec in capabilities.items()
    }

    drift: List[str] = []

    # Build project -> set(global capabilities it declares) from the manifests.
    declared: Dict[str, set] = {}
    for manifest_path in sorted(manifests_dir.glob("*.mcp.yaml")):
        manifest = _load(manifest_path)
        project = manifest.get("project")
        if not project:
            drift.append(f"{manifest_path.name}: missing 'project'")
            continue
        all_declared = set(manifest.get("inherits", []) or []) | set(
            manifest.get("capabilities", []) or []
        )
        declared[project] = all_declared & global_names

    # extra — a manifest declares a global capability it isn't required_by.
    for project in sorted(declared):
        expected = {c for c, projects in required_by.items() if project in projects}
        for cap in sorted(declared[project] - expected):
            drift.append(
                f"{project}: declares {cap!r} but is not in its required_by"
            )

    # missing — a capability's required_by names a project that doesn't
    # declare it, including a project with no manifest at all (so a typo or a
    # not-yet-onboarded project in required_by is caught, not silently passed).
    for cap in sorted(required_by):
        for project in sorted(required_by[cap]):
            if project not in declared:
                drift.append(
                    f"{cap}: required_by {project!r} but no manifest declares it"
                )
            elif cap not in declared[project]:
                drift.append(
                    f"{project}: required_by {cap!r} but the manifest does not "
                    f"declare it"
                )
    return drift


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=_DEFAULT_REGISTRY)
    parser.add_argument("--manifests", type=Path, default=_DEFAULT_MANIFESTS)
    args = parser.parse_args(argv)

    drift = find_drift(args.registry, args.manifests)
    if drift:
        print("Registry drift detected:")
        for message in drift:
            print(f"  - {message}")
        return 1

    count = len(list(args.manifests.glob("*.mcp.yaml")))
    print(f"No registry drift across {count} project(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
