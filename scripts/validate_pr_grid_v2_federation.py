#!/usr/bin/env python3
"""Validate PR_GRID_GEOGRAPHIC_V2 pin and runtime parity across the federation.

TheHub is the federation control plane, not the geometry authority. This command
proves that all six consumers reference one immutable Spiderweb RC1 contract and
that all five producer-consumers carry the byte-identical shared runtime.
Missing consumers, missing runtimes, or runtime drift are failures, not skips.
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

PIN_REL = Path("federation/spatial/pr_grid_geographic_v2.pin.json")
RUNTIME_REL = Path("federation/spatial/pr_grid_v2_runtime.py")
CANONICAL_RUNTIME = REPO_ROOT / "src/hub/grid_v2.py"
RUNTIME_CONSUMERS = frozenset(EXPECTED_CONSUMERS - {"thehub-pr"})


def _pin_paths(workspace_root: Path) -> dict:
    paths = {}
    for consumer in sorted(EXPECTED_CONSUMERS):
        repo_root = REPO_ROOT if consumer == "thehub-pr" else workspace_root / consumer
        paths[consumer] = repo_root / PIN_REL
    return paths


def _runtime_paths(workspace_root: Path) -> dict:
    return {
        consumer: workspace_root / consumer / RUNTIME_REL
        for consumer in sorted(RUNTIME_CONSUMERS)
    }


def _validate_runtime_set(workspace_root: Path) -> tuple[str, dict]:
    try:
        canonical_bytes = CANONICAL_RUNTIME.read_bytes()
    except OSError as exc:
        raise GridV2PinError(
            f"cannot read canonical V2 runtime {CANONICAL_RUNTIME}: {exc}"
        ) from exc

    canonical_sha = hashlib.sha256(canonical_bytes).hexdigest()
    paths = _runtime_paths(workspace_root)
    details = {}
    for consumer, path in sorted(paths.items()):
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise GridV2PinError(
                f"missing V2 runtime for {consumer} at {path}: {exc}"
            ) from exc
        digest = hashlib.sha256(payload).hexdigest()
        if payload != canonical_bytes:
            raise GridV2PinError(
                f"V2 runtime drift for {consumer}: "
                f"expected_sha256={canonical_sha} observed_sha256={digest}"
            )
        details[consumer] = {
            "runtime_path": str(path),
            "runtime_sha256": digest,
            "bytes": len(payload),
        }
    return canonical_sha, details


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=REPO_ROOT.parent,
        help="directory containing sibling federation repositories",
    )
    args = parser.parse_args()
    workspace_root = args.workspace_root.resolve()

    paths = _pin_paths(workspace_root)
    try:
        pins = validate_pin_set(paths)
        runtime_sha256, runtime_details = _validate_runtime_set(workspace_root)
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
                    "runtime_paths": {
                        k: str(v)
                        for k, v in sorted(_runtime_paths(workspace_root).items())
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
        "runtime_consumer_count": len(runtime_details),
        "Grid_ID": GRID_ID,
        "Grid_Version": GRID_VERSION,
        "Authority_Commit": AUTHORITY_COMMIT,
        "Grid_Manifest_SHA256": GRID_MANIFEST_SHA256,
        "Runtime_SHA256": runtime_sha256,
        "consumers": {
            consumer: {
                "pin_path": str(paths[consumer]),
                "default_level": pin.default_level,
                "identity": grid_identity(pin),
            }
            for consumer, pin in sorted(pins.items())
        },
        "runtimes": runtime_details,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
