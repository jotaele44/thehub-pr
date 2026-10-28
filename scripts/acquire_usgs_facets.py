"""Acquire or reuse one bounded, explicit USGS facet snapshot."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hub.usgs_facet_snapshot import acquire_facet_snapshot  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = acquire_facet_snapshot(
        ROOT / "registry/usgs/facet_acquisition_plan.v1.json",
        args.out,
        args.snapshot_id,
    )
    print(json.dumps({k: v for k, v in report.items() if k != "receipts"}, indent=2))
    return 0 if report["state"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
