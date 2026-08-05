#!/usr/bin/env python3
"""Validate and materialize a Skywatcher sensor-fusion export for TheHub."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hub.sensor_fusion_consumer import write_dashboard_surface


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", default=Path("data/dashboard/skywatcher_sensor_fusion.json"), type=Path)
    args = parser.parse_args()

    surface = write_dashboard_surface(args.input, args.output)
    print(json.dumps({"valid": surface["valid"], "output": str(args.output)}, sort_keys=True))
    return 0 if surface["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
