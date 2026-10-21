#!/usr/bin/env python3
"""Validate the complete PR_GRID_GEOGRAPHIC_V2 consumer pin denominator.

TheHub is the federation control plane, not the geometry authority. This command
proves that all six consumers reference the same immutable Spiderweb RC1
contract and that the Spiderweb checkout is the exact pinned authority commit.
Missing consumers or mismatched authority state fail closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hub.grid_v2 import (  # noqa: E402
    AUTHORITY_COMMIT,
    EXPECTED_CONSUMERS,
    GRID_ID,
    GRID_MANIFEST_SHA256,
    GRID_VERSION,
    GridV2PinError,
    grid_identity,
    validate_pin_set,
)
from hub.grid_v2_authority import (  # noqa: E402
    validate_authority_root,
    validate_frozen_pin_denominator,
)

PIN_REL = Path("federation/spatial/pr_grid_geographic_v2.pin.json")

SHARED_CONSUMER_FILES = {
    "federation/spatial/pr_grid_v2_runtime.py":
        REPO_ROOT / "federation-templates/spatial/pr_grid_v2_runtime.py",
    "federation/spatial/pr_grid_v2_profiles.py":
        REPO_ROOT / "federation-templates/spatial/pr_grid_v2_profiles.py",
    "federation/spatial/materialize_pr_grid_v2_profiles.py":
        REPO_ROOT / "federation-templates/spatial/materialize_pr_grid_v2_profiles.py",
    "server/backend/grid_v2_api.py":
        REPO_ROOT / "federation-templates/spatial/pr_grid_v2_api.py",
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _validate_shared_consumer_runtime(workspace_root: Path) -> dict[str, object]:
    expected_consumers = sorted(EXPECTED_CONSUMERS - {"thehub-pr"})
    files: dict[str, dict[str, object]] = {}
    for output_rel, template_path in SHARED_CONSUMER_FILES.items():
        try:
            expected = template_path.read_bytes()
        except OSError as exc:
            raise GridV2PinError(
                f"cannot read shared V2 template {template_path}: {exc}"
            ) from exc
        per_repo = {}
        for consumer in expected_consumers:
            path = workspace_root / consumer / output_rel
            try:
                observed = path.read_bytes()
            except OSError as exc:
                raise GridV2PinError(
                    f"missing shared V2 runtime file for {consumer}: {output_rel}: {exc}"
                ) from exc
            if observed != expected:
                raise GridV2PinError(
                    f"shared V2 runtime drift: {consumer}:{output_rel}"
                )
            per_repo[consumer] = _sha256(observed)
        files[output_rel] = {
            "Template_SHA256": _sha256(expected),
            "Consumer_SHA256": per_repo,
            "State": "BYTE_IDENTICAL_PASS",
        }
    return {
        "Expected_Consumer_Count": len(expected_consumers),
        "Verified_Consumer_Count": len(expected_consumers),
        "Geometry_Producer": "spiderweb-pr",
        "Consumer_Geometry_Mode": "REFERENCE_ONLY",
        "Files": files,
        "State": "SHARED_RUNTIME_PARITY_PASS",
    }


def _pin_paths(workspace_root: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for consumer in sorted(EXPECTED_CONSUMERS):
        repo_root = (
            REPO_ROOT if consumer == "thehub-pr" else workspace_root / consumer
        )
        paths[consumer] = repo_root / PIN_REL
    return paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=REPO_ROOT.parent,
        help="directory containing sibling federation repositories",
    )
    parser.add_argument(
        "--authority-root",
        type=Path,
        help="Spiderweb checkout; defaults to workspace sibling",
    )
    args = parser.parse_args()

    workspace_root = args.workspace_root.resolve()
    paths = _pin_paths(workspace_root)

    try:
        pins = validate_pin_set(paths)
        authority_root = args.authority_root or (workspace_root / "spiderweb-pr")
        authority = validate_authority_root(
            authority_root.resolve(),
            verify_commit_object=True,
        )
        denominator = validate_frozen_pin_denominator(
            paths,
            REPO_ROOT / "registry/spatial/v2/consumer_pin_denominator.json",
        )
        shared_runtime = _validate_shared_consumer_runtime(workspace_root)
    except GridV2PinError as exc:
        print(
            json.dumps(
                {
                    "state": "FAIL_CLOSED",
                    "Grid_ID": GRID_ID,
                    "Grid_Version": GRID_VERSION,
                    "Authority_Commit": AUTHORITY_COMMIT,
                    "Grid_Manifest_SHA256": GRID_MANIFEST_SHA256,
                    "error": str(exc),
                    "pin_paths": {
                        key: str(value)
                        for key, value in sorted(paths.items())
                    },
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    payload = {
        "state": "PASS",
        "consumer_count": len(pins),
        "authority_source_validation": authority,
        "frozen_denominator": denominator,
        "shared_consumer_runtime": shared_runtime,
        "Grid_ID": GRID_ID,
        "Grid_Version": GRID_VERSION,
        "Authority_Commit": AUTHORITY_COMMIT,
        "Grid_Manifest_SHA256": GRID_MANIFEST_SHA256,
        "consumers": {
            consumer: {
                "pin_path": str(paths[consumer]),
                "default_level": pin.default_level,
                "identity": grid_identity(pin),
            }
            for consumer, pin in sorted(pins.items())
        },
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
