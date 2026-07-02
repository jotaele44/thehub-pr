#!/usr/bin/env python3
"""Build a data-population and threshold-tuning report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hub.threshold_tuning import build_tuning_report


def read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                rows.append(json.loads(text))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, default=Path("data/federation_analytics_v2/records.jsonl"))
    parser.add_argument("--scored-events", type=Path, default=Path("data/federation_analytics_v2/scored_events.jsonl"))
    parser.add_argument("--labels", type=Path, default=Path("data/federation_analytics_v2/labels.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/federation_analytics_v2/threshold_tuning_report.json"))
    args = parser.parse_args()

    report = build_tuning_report(read_jsonl(args.records), read_jsonl(args.scored_events), read_jsonl(args.labels))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "population_ready": report["population"]["population_ready"]}, sort_keys=True))
    return 0 if report["population"]["population_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
