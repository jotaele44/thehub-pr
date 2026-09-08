#!/usr/bin/env python3
"""Canonical CLI entry point for authority-boundary validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from authority_boundary_validator import (
    load_json,
    repository_paths,
    validate as validate_base,
)
from identifier_namespace_census import validate as validate_identifier_v2


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--peer-root", default="_authority_peers")
    parser.add_argument(
        "--report", default="reports/authority_boundary_validation.json"
    )
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    peer_root = Path(args.peer_root).resolve()

    report = validate_base(root, peer_root)

    snapshots = load_json(root / "registry/federation/repository_snapshots.json")
    rows = snapshots.get("repositories", [])
    paths = repository_paths(root, peer_root, rows)
    identifier_registry = load_json(
        root / "registry/federation/identifier_namespaces.json"
    )
    id_blockers, id_detail = validate_identifier_v2(paths, identifier_registry)
    report["blockers"].extend(id_blockers)
    report["findings"].append(
        {"id": "STRUCTURED_IDENTIFIER_CENSUS_V2", "detail": id_detail}
    )

    report["schema_version"] = "authority_boundary_validation_v3"
    report["blocker_count"] = len(report["blockers"])
    report["certification"] = (
        "AUTHORITY_BOUNDARY_CERTIFIED" if not report["blockers"] else "NOT_CERTIFIED"
    )
    report["next_phase"] = (
        "A_FEDERATION_IDENTITY_CONTRACT" if not report["blockers"] else "BLOCKED"
    )

    output = Path(args.report)
    if not output.is_absolute():
        output = root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not report["blockers"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
