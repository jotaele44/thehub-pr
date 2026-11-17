#!/usr/bin/env python3
"""Tabulate the element detail from the Chromium runtime pass.

Reads the per-application outputs of scripts/runtime/chromium_pass.js and
writes, for the four rules a fix has to be traced to a component, each distinct
failing element: its markup, the routes and widths it failed at and, for
contrast, the colours axe measured.

An element is "shared" when its own class list carries a design-system class
(``fd-``), and "application" otherwise. That is a statement about which
stylesheet colours or shapes the element, read off its markup; it decides
nothing else.

Usage:
  rc3_runtime_detail.py <dir with out-<repository>.json> <output json>
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

RULES = ("color-contrast", "button-name", "scrollable-region-focusable", "label-content-name-mismatch")
CLASS = re.compile(r'^<[a-zA-Z0-9-]+[^>]*?\sclass="([^"]*)"')


def styled_by(html: str) -> str:
    match = CLASS.match(html)
    classes = match.group(1).split() if match else []
    return "shared" if any(name.startswith("fd-") for name in classes) else "application"


def tabulate(path: Path) -> dict:
    data = json.loads(path.read_text())
    loads = data["observations"]
    routes = sorted({row["route"] for row in loads})
    rules: dict[str, dict] = {}
    for rule in RULES:
        elements: dict[tuple, dict] = {}
        failing_routes: set[str] = set()
        for row in loads:
            for violation in row.get("axe") or []:
                if violation["id"] != rule:
                    continue
                failing_routes.add(row["route"])
                for node in violation.get("detail", []):
                    key = (node["html"], node.get("fg"), node.get("bg"))
                    entry = elements.setdefault(
                        key,
                        {
                            "html": node["html"],
                            "styled_by": styled_by(node["html"]),
                            "routes": set(),
                            "widths": set(),
                            "example_selector": node["target"],
                        },
                    )
                    for field in ("fg", "bg", "ratio", "expected", "font_size", "font_weight"):
                        if field in node:
                            entry[field] = node[field]
                    entry["routes"].add(row["route"])
                    entry["widths"].add(row["width"])
        if not elements and not failing_routes:
            continue
        listed = sorted(elements.values(), key=lambda e: (-len(e["routes"]), e["html"]))
        for entry in listed:
            entry["route_count"] = len(entry["routes"])
            entry["routes"] = sorted(entry["routes"])[:5]
            entry["widths"] = sorted(entry["widths"])
        summary = {
            "routes_failing": len(failing_routes),
            "distinct_elements": len(listed),
            "styled_by": {
                kind: sum(1 for e in listed if e["styled_by"] == kind) for kind in ("shared", "application")
            },
            "elements": listed,
        }
        if rule == "color-contrast":
            pairs: dict[tuple, dict] = defaultdict(lambda: {"elements": 0, "routes": set()})
            for entry in listed:
                pair = pairs[(entry.get("fg"), entry.get("bg"), entry.get("ratio"), entry.get("font_size"))]
                pair["elements"] += 1
                pair["routes"].update(entry["routes"])
            summary["colour_pairs"] = [
                {
                    "fg": fg,
                    "bg": bg,
                    "ratio": ratio,
                    "font_size": size,
                    "distinct_elements": value["elements"],
                }
                for (fg, bg, ratio, size), value in sorted(
                    pairs.items(), key=lambda item: -item[1]["elements"]
                )
            ]
        rules[rule] = summary
    return {
        "repository": data["repository"],
        "axe_version": data.get("axe_version"),
        "csp_bypassed_for_scan": data.get("csp_bypassed_for_scan", False),
        "routes": len(routes),
        "page_loads": len(loads),
        "rules": rules,
    }


def main() -> None:
    source, output = Path(sys.argv[1]), Path(sys.argv[2])
    applications = [tabulate(path) for path in sorted(source.glob("out-*.json"))]
    totals = {
        rule: {
            kind: sum(app["rules"].get(rule, {}).get("styled_by", {}).get(kind, 0) for app in applications)
            for kind in ("shared", "application")
        }
        for rule in RULES
    }
    document = {
        "schema": "federation.experience-program.runtime-element-detail/1",
        "method": (
            "Chromium, dark colour scheme, every addressable route at 320, 390, 430, 768, 1280, 1440 and "
            "1920 CSS pixels. Pages were loaded, not operated. An element is counted once per application "
            "however many routes and widths it failed at; routes lists at most five. Element lists are "
            "capped at 80 per rule per page load by the scan."
        ),
        "styled_by_rule": (
            "shared = the element's own class list has a design-system (fd-) class; "
            "application = it does not."
        ),
        "distinct_elements_by_rule": totals,
        "applications": applications,
    }
    output.write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n")
    for rule, counts in totals.items():
        print(rule, counts)


if __name__ == "__main__":
    main()
