#!/usr/bin/env python3
"""Compare two runtime passes of one application: before and after a pilot.

Both inputs are raw outputs of scripts/runtime/chromium_pass.js for the same
routes and widths. Everything written is recomputed from them. The script
reports; it sets no state.

Usage:
  rc4_pilot_compare.py --before <out-<repository>.json> --after <out-<repository>.json>
                       --before-commit <sha> --after-commit <sha> --out <json>
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rc3_runtime_detail import RULES, tabulate  # noqa: E402

BLOCKING = ("critical", "serious")


def all_rules(path: Path) -> dict:
    """Page loads and routes on which each critical or serious rule fired."""
    loads = json.loads(path.read_text())["observations"]
    page_loads: Counter = Counter()
    routes: dict[str, set] = {}
    for row in loads:
        for violation in row.get("axe") or []:
            if violation["impact"] in BLOCKING:
                page_loads[violation["id"]] += 1
                routes.setdefault(violation["id"], set()).add(row["route"])
    return {
        rule: {"page_loads": page_loads[rule], "routes": len(routes[rule])} for rule in sorted(page_loads)
    }


def frame(path: Path) -> dict:
    loads = json.loads(path.read_text())["observations"]
    by_route: dict[str, list] = {}
    for row in loads:
        by_route.setdefault(row["route"], []).append(row)
    redirected = sorted(
        route
        for route, rows in by_route.items()
        if any(row.get("final_path", route).split("?")[0] != route.split("?")[0] for row in rows)
    )
    return {
        "routes": len(by_route),
        "page_loads": len(loads),
        "page_loads_with_an_error": sum(1 for row in loads if "error" in row),
        "page_loads_not_200": sum(1 for row in loads if row.get("status") != 200),
        "routes_that_redirect": redirected,
        "page_loads_with_horizontal_overflow": sum(
            1 for row in loads if row.get("horizontal_overflow_px", 0) > 0
        ),
        "page_loads_with_an_unnamed_button": sum(1 for row in loads if row.get("unnamed_buttons", 0) > 0),
        "controls_under_24px_summed_over_page_loads": sum(row.get("controls_under_24px", 0) for row in loads),
        "page_loads_with_console_errors": sum(1 for row in loads if row.get("console_errors", 0) > 0),
        "page_loads_with_page_errors": sum(1 for row in loads if row.get("page_errors")),
    }


def targeted(table: dict) -> dict:
    out = {}
    for rule in RULES:
        summary = table["rules"].get(rule)
        out[rule] = {
            "routes_failing": summary["routes_failing"] if summary else 0,
            "distinct_elements": summary["distinct_elements"] if summary else 0,
            "elements": [
                {key: element[key] for key in ("html", "route_count", "routes", "widths") if key in element}
                for element in (summary["elements"] if summary else [])
            ],
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("before", "after", "before-commit", "after-commit", "out"):
        parser.add_argument(f"--{name}", required=True)
    args = parser.parse_args()
    before_path, after_path = Path(args.before), Path(args.after)
    before, after = tabulate(before_path), tabulate(after_path)
    if before["repository"] != after["repository"]:
        raise SystemExit("the two passes are of different applications")
    before_rules, after_rules = all_rules(before_path), all_rules(after_path)
    document = {
        "schema": "federation.experience-program.pilot-comparison/1",
        "claim_class": "COMPUTED",
        "repository": before["repository"],
        "commits": {"before": args.before_commit, "after": args.after_commit},
        "method": (
            "Chromium, dark colour scheme, the same routes at 320, 390, 430, 768, 1280, 1440 and 1920 CSS "
            "pixels, on a fresh temporary workspace. Pages were loaded, not operated."
        ),
        "frame": {"before": frame(before_path), "after": frame(after_path)},
        "targeted_rules": {
            rule: {"before": targeted(before)[rule], "after": targeted(after)[rule]} for rule in RULES
        },
        "every_critical_or_serious_rule": {
            rule: {
                "before": before_rules.get(rule, {"page_loads": 0, "routes": 0}),
                "after": after_rules.get(rule, {"page_loads": 0, "routes": 0}),
            }
            for rule in sorted(set(before_rules) | set(after_rules))
        },
    }
    # The elements of the "before" side are already in rc3/runtime_element_detail.json.
    for value in document["targeted_rules"].values():
        value["before"] = {key: item for key, item in value["before"].items() if key != "elements"}
    Path(args.out).write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n")
    for rule, value in document["targeted_rules"].items():
        print(rule, value["before"]["distinct_elements"], "->", value["after"]["distinct_elements"])
    for rule, value in document["every_critical_or_serious_rule"].items():
        print("  all:", rule, value["before"], "->", value["after"])


if __name__ == "__main__":
    main()
