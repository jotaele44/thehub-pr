"""Internal acquisition job. A new --out explicitly creates a new snapshot."""
import argparse
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hub.usgs_acquisition import snapshot_item  # noqa: E402
from hub.usgs_catalog import load_catalog  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=6, choices=range(1, 13))
    args = parser.parse_args()
    catalog = load_catalog()
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        results = list(executor.map(lambda r: snapshot_item(r["sciencebase_id"], args.out), catalog["releases"]))
    assert len(results) == catalog["counts"]["included"]
    summary = {"source_workbook_sha256": catalog["source"]["sha256"], "attempted": len(results),
               "metadata_states": dict(Counter(r["state"] for r in results)),
               "enumeration_states": dict(Counter(r["enumeration_state"] for r in results)),
               "http_statuses": dict(Counter(str(r["http_status"]) for r in results)),
               "payload_state": "BLOCKED", "activated": 0, "receipts": results}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "receipts"}))
    return 0 if all(r["enumeration_state"] == "PASS" for r in results) else 2


if __name__ == "__main__":
    sys.exit(main())
