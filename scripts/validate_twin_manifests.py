#!/usr/bin/env python3
"""Validate the Twin observed and Federation-derived capability manifests.

Checks both manifests against their schemas and the rules in
``hub.twin_manifest`` (closed 223-row observed census, one canonical owner per
row, explicit dispositions, no derived entry leaking into the observed
denominator) and verifies each ``reconciliation`` block matches its rows.

Usage:
    python3 scripts/validate_twin_manifests.py            # check (CI)
    python3 scripts/validate_twin_manifests.py --write    # refresh reconciliation blocks
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hub.twin_manifest import check_repo  # noqa: E402


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root (default: this checkout)")
    parser.add_argument("--write", action="store_true", help="rewrite reconciliation blocks from the rows")
    args = parser.parse_args(argv)
    errors = check_repo(args.root, write=args.write)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    print("twin manifests OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
