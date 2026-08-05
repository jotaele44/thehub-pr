#!/usr/bin/env python3
"""Generate the per-producer capability contract TheHub expects each producer
to declare, derived from the registry ``required_by`` lists.

This is the testable core of cross-repo synchronization: it produces the
artifact a sync job would propagate to each sibling producer repo. The actual
cross-repo write (opening a PR / dispatching to the sibling repo) needs an
operator PAT and each producer's config layout, and is intentionally NOT done
here — see .github/workflows/mcp-cross-repo-sync.yml.

Standalone (PyYAML only). Prints a combined JSON to stdout, or with
``--out-dir`` writes one ``<project>.capabilities.json`` per producer.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_REGISTRY = _REPO_ROOT / "mcp" / "registry" / "capability_registry.yaml"


def build_artifacts(registry_path: Path) -> Dict[str, Dict]:
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    capabilities: Dict[str, dict] = registry.get("capabilities", {}) or {}

    projects: Dict[str, List[str]] = {}
    for name, spec in capabilities.items():
        for project in spec.get("required_by", []) or []:
            projects.setdefault(project, []).append(name)

    return {
        project: {
            "project": project,
            "hub": "thehub-pr",
            "expected_capabilities": sorted(caps),
        }
        for project, caps in sorted(projects.items())
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=_DEFAULT_REGISTRY)
    parser.add_argument(
        "--out-dir", type=Path,
        help="write one <project>.capabilities.json per producer here",
    )
    args = parser.parse_args(argv)

    artifacts = build_artifacts(args.registry)
    if args.out_dir:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        for project, artifact in artifacts.items():
            path = args.out_dir / f"{project}.capabilities.json"
            path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
        print(f"Wrote {len(artifacts)} producer contract(s) to {args.out_dir}")
    else:
        print(json.dumps(artifacts, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
