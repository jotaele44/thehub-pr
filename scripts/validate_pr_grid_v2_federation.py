#!/usr/bin/env python3
"""Validate the complete PR_GRID_GEOGRAPHIC_V2 consumer pin denominator.

TheHub is the federation control plane, not the geometry authority. This command
only proves that all six consumers reference the same immutable Spiderweb RC1
contract. Missing consumers are failures, not skips.
"""
from __future__ import annotations

import argparse
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

PIN_REL = Path("federation/spatial/pr_grid_geographic_v2.pin.json")


def _pin_paths(workspace_root: Path) -> dict:
    paths = {}
    for consumer in sorted(EXPECTED_CONSUMERS):
        repo_root = REPO_ROOT if consumer == "thehub-pr" else workspace_root / consumer
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
    args = parser.parse_args()

    paths = _pin_paths(args.workspace_root.resolve())
    try:
        pins = validate_pin_set(paths)
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
                    "pin_paths": {k: str(v) for k, v in sorted(paths.items())},
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    payload = {
        "state": "PASS",
        "consumer_count": len(pins),
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
