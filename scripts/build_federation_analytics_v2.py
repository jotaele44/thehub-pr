#!/usr/bin/env python3
"""Build Federation Analytics v2 payload from local JSONL/JSON inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hub.federation_analytics_v2 import build_federation_analytics_v2_payload


def read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    records: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                records.append(json.loads(text))
    return records


def read_json_records(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("anomalies", "events", "records", "cross_repo_events"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records-jsonl", type=Path, default=Path("data/federation_analytics_v2/records.jsonl"))
    parser.add_argument("--anomalies-json", type=Path, default=Path("data/federation_analytics_v2/anomalies.json"))
    parser.add_argument("--output", type=Path, default=Path("data/federation_analytics_v2/federation_analytics_v2.json"))
    args = parser.parse_args()

    records = read_jsonl(args.records_jsonl)
    anomalies = read_json_records(args.anomalies_json)
    payload = build_federation_analytics_v2_payload(records, anomalies)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"release": payload["release"], "output": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
