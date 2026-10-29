#!/usr/bin/env python3
"""Validate the frozen PR Grid V2 domain migration-readiness denominator.

This validator is intentionally stdlib-only. It certifies governance semantics,
not remote source availability. Remote evidence identities are frozen in the
ledger and are verified separately by cross-repo workflows.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

GRID_ID = "PR_GRID_GEOGRAPHIC_V2"
GRID_VERSION = "2.0.0-rc1"
CRS = "EPSG:6566"
GRID_MANIFEST_SHA256 = "8902af188ad449955119016f5747fe2393c582d9ed552fb03bcaecd9ab510aa4"
AUTHORITY = "spiderweb-pr"
AUTHORITY_COMMIT = "0c66e13d14232c0d7cbcbc179b3655904777dc71"

EXPECTED_LEVELS = {
    "aguayluz-pr": "L1",
    "skywatcher-pr": "L2",
    "ovnis-pr": "L1",
    "moneysweep-pr": "L1",
    "centinelas-pr": "L0",
}
EXPECTED_PASS = {"aguayluz-pr"}
EXPECTED_BLOCKED = set(EXPECTED_LEVELS) - EXPECTED_PASS

FORBIDDEN_PRODUCTION_SOURCE_MARKERS = (
    "/tests/",
    "tests/",
    "/fixtures/",
    "fixtures/",
    "/samples/",
    "samples/",
    "/conformance/",
    "conformance/",
)


class ReadinessError(ValueError):
    """Raised when the migration-readiness ledger violates a frozen invariant."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReadinessError(message)


def _validate_evidence(row: dict[str, Any]) -> None:
    evidence = row.get("evidence")
    _require(isinstance(evidence, list) and evidence, f"{row['repository']}: evidence is required")
    for item in evidence:
        _require(isinstance(item, dict), f"{row['repository']}: evidence row must be an object")
        role = item.get("role")
        _require(
            role in {"SOURCE", "CERTIFICATION_WORKFLOW", "BLOCKER_EVIDENCE"},
            f"{row['repository']}: invalid evidence role {role!r}",
        )
        repository = item.get("repository")
        path = item.get("path")
        _require(
            isinstance(repository, str) and "/" in repository,
            f"{row['repository']}: evidence repository must be owner/name",
        )
        _require(isinstance(path, str) and path.strip(), f"{row['repository']}: evidence path required")

        if role == "SOURCE":
            normalized = "/" + path.strip("/") + "/"
            for marker in FORBIDDEN_PRODUCTION_SOURCE_MARKERS:
                _require(
                    marker not in normalized,
                    f"{row['repository']}: production SOURCE cannot use {marker.strip('/')}",
                )
            _require(
                isinstance(item.get("frozen_commit"), str)
                and len(item["frozen_commit"]) == 40,
                f"{row['repository']}: production SOURCE requires frozen_commit",
            )
            _require(
                isinstance(item.get("git_blob_sha1"), str)
                and len(item["git_blob_sha1"]) == 40,
                f"{row['repository']}: production SOURCE requires git_blob_sha1",
            )


def validate_ledger(payload: dict[str, Any]) -> None:
    _require(
        payload.get("schema_version") == "pr-grid-v2-migration-readiness/1.0",
        "wrong schema_version",
    )

    identity = payload.get("grid_identity")
    _require(isinstance(identity, dict), "grid_identity must be an object")
    expected_identity = {
        "Grid_ID": GRID_ID,
        "Grid_Version": GRID_VERSION,
        "CRS": CRS,
        "Grid_Manifest_SHA256": GRID_MANIFEST_SHA256,
        "Geometry_Authority": AUTHORITY,
        "Authority_Commit": AUTHORITY_COMMIT,
    }
    _require(identity == expected_identity, "grid_identity does not match frozen Spiderweb authority")

    domains = payload.get("domain_denominator")
    _require(isinstance(domains, list), "domain_denominator must be an array")
    _require(len(domains) == 5, "domain_denominator must contain exactly five domain consumers")

    by_repo: dict[str, dict[str, Any]] = {}
    for row in domains:
        _require(isinstance(row, dict), "domain denominator row must be an object")
        repo = row.get("repository")
        _require(repo in EXPECTED_LEVELS, f"unexpected repository {repo!r}")
        _require(repo not in by_repo, f"duplicate repository {repo}")
        by_repo[repo] = row
        _require(
            row.get("default_level") == EXPECTED_LEVELS[repo],
            f"{repo}: wrong default_level",
        )
        _validate_evidence(row)

        state = row.get("readiness_state")
        _require(state in {"PASS", "BLOCKED"}, f"{repo}: invalid readiness_state")
        blockers = row.get("blocker_codes")
        _require(isinstance(blockers, list), f"{repo}: blocker_codes must be a list")

        if state == "PASS":
            _require(row.get("exact_binding_permitted") is True, f"{repo}: PASS must permit exact binding")
            _require(
                row.get("production_profile_permitted") is True,
                f"{repo}: PASS must permit production profile materialization",
            )
            _require(not blockers, f"{repo}: PASS cannot retain blocker_codes")
            _require(
                row.get("migration_class")
                in {"RECOMPUTED_FROM_SOURCE_COORDINATE", "RECOMPUTED_FROM_SOURCE_GEOMETRY"},
                f"{repo}: PASS requires an exact source migration class",
            )
            _require(
                any(item.get("role") == "SOURCE" for item in row["evidence"]),
                f"{repo}: PASS requires frozen SOURCE evidence",
            )
        else:
            _require(row.get("exact_binding_permitted") is False, f"{repo}: BLOCKED cannot permit exact binding")
            _require(
                row.get("production_profile_permitted") is False,
                f"{repo}: BLOCKED cannot permit production profiles",
            )
            _require(row.get("migration_class") is None, f"{repo}: BLOCKED migration_class must be null")
            _require(bool(blockers), f"{repo}: BLOCKED requires blocker_codes")
            next_evidence = row.get("required_next_evidence")
            _require(
                isinstance(next_evidence, list) and next_evidence,
                f"{repo}: BLOCKED requires required_next_evidence",
            )

    _require(set(by_repo) == set(EXPECTED_LEVELS), "domain denominator membership mismatch")
    pass_repos = {repo for repo, row in by_repo.items() if row["readiness_state"] == "PASS"}
    blocked_repos = {repo for repo, row in by_repo.items() if row["readiness_state"] == "BLOCKED"}
    _require(pass_repos == EXPECTED_PASS, f"PASS denominator changed: {sorted(pass_repos)}")
    _require(blocked_repos == EXPECTED_BLOCKED, f"BLOCKED denominator changed: {sorted(blocked_repos)}")

    control = payload.get("control_plane")
    _require(isinstance(control, dict), "control_plane must be an object")
    _require(control.get("repository") == "thehub-pr", "TheHub must own the control-plane ledger")
    _require(
        control.get("role") == "VALIDATE_AND_AGGREGATE_REFERENCE_ONLY",
        "TheHub role must remain reference-only",
    )
    _require(control.get("geometry_authority") is False, "TheHub cannot become geometry authority")
    _require(control.get("expected_domain_count") == 5, "expected_domain_count must remain five")
    _require(set(control.get("current_pass_domains", [])) == pass_repos, "control-plane PASS rollup mismatch")
    _require(
        set(control.get("current_blocked_domains", [])) == blocked_repos,
        "control-plane BLOCKED rollup mismatch",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ledger",
        type=Path,
        default=Path("federation/spatial/pr_grid_v2_migration_readiness.json"),
    )
    args = parser.parse_args()
    try:
        payload = json.loads(args.ledger.read_text(encoding="utf-8"))
        _require(isinstance(payload, dict), "ledger root must be an object")
        validate_ledger(payload)
    except (OSError, json.JSONDecodeError, ReadinessError) as exc:
        parser.exit(2, f"FAIL_CLOSED: {exc}\n")
    print("PR_GRID_V2_MIGRATION_READINESS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
