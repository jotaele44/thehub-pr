"""Offline nested file-reference discovery; never acquires or activates payloads."""

import argparse
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hub.usgs_nested_inventory import inventory_nested_files  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        raise ValueError("Preserve previous nested inventory")
    baseline = json.loads(
        gzip.decompress(
            (ROOT / "data/usgs/continuation_inventory.v1.json.gz").read_bytes()
        )
    )
    roots = [
        r["sciencebase_id"]
        for r in json.loads((ROOT / "registry/usgs/pr_releases.v1.json").read_text())[
            "releases"
        ]
    ]
    report = inventory_nested_files(
        ROOT / "data/usgs/snapshots/20261016_all_item_metadata.zip",
        "5f0c4f3b4782ed9a9c94511a76fdda0b6ac82e9caba8075219cb15f461b4f280",
        baseline,
        roots,
    )
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_bytes(
        gzip.compress((json.dumps(report, indent=2) + "\n").encode(), mtime=0)
    )
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k
                not in ("references", "metadata_receipts", "non_array_files_fields")
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
