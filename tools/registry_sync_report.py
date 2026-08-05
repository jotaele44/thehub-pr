#!/usr/bin/env python3
"""Emit a machine-readable registry/manifest sync report (JSON).

Reuses ``check_registry_drift.find_drift`` (the same drift semantics enforced
in CI) and adds a per-project view of declared vs expected global
capabilities, so a dashboard or a downstream sync job can consume the state
without re-implementing the comparison. Standalone (PyYAML only); always
exits 0 — this is a reporting tool, not a gate (use
``check_registry_drift.py`` for the gate).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_registry_drift import (  # noqa: E402
    _DEFAULT_MANIFESTS,
    _DEFAULT_REGISTRY,
    find_drift,
)


def build_report(registry_path: Path, manifests_dir: Path) -> Dict:
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    capabilities: Dict[str, dict] = registry.get("capabilities", {}) or {}
    global_names = set(capabilities)
    required_by = {
        name: set(spec.get("required_by", []) or [])
        for name, spec in capabilities.items()
    }

    projects: Dict[str, Dict[str, List[str]]] = {}
    for manifest_path in sorted(manifests_dir.glob("*.mcp.yaml")):
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        project = manifest.get("project")
        if not project:
            continue
        declared = set(manifest.get("inherits", []) or []) | set(
            manifest.get("capabilities", []) or []
        )
        global_declared = declared & global_names
        expected = {c for c, projs in required_by.items() if project in projs}
        projects[project] = {
            "declared": sorted(global_declared),
            "expected": sorted(expected),
            "missing": sorted(expected - global_declared),
            "extra": sorted(global_declared - expected),
        }

    drift = find_drift(registry_path, manifests_dir)
    return {
        "in_sync": not drift,
        "drift": drift,
        "project_count": len(projects),
        "projects": projects,
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=_DEFAULT_REGISTRY)
    parser.add_argument("--manifests", type=Path, default=_DEFAULT_MANIFESTS)
    parser.add_argument("--out", type=Path, help="write JSON here (default: stdout)")
    args = parser.parse_args(argv)

    report = build_report(args.registry, args.manifests)
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
