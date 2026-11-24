#!/usr/bin/env python3
"""Build the evidence a pilot choice for RC4 rests on.

Two outputs, both recomputed from recorded data and deciding nothing:

* ``thehub_rescan.json``: the thehub-pr rows of the RC3 element list set
  beside a re-scan of a later commit, per rule.
* ``RC4_PLAN_INPUT.json``: one row per application with its distinct failing
  elements per rule, how concentrated they are, its design-system pin, and
  whether its audited tree is still current.

"Style signatures" is the number of distinct tag-and-class combinations among
an application's failing elements. It is a proxy for how many places a fix has
to touch, read off the markup; it is not a count of source files.

Usage:
  rc4_pilot_input.py --rc3 <runtime_element_detail.json> --rescan <dir with out-thehub-pr.json>
                     --audited-raw <out-thehub-pr.json of the audited commit>
                     --rescan-commit <sha> --drift <main_drift.json> --pins <pins.json> --out <rc4 dir>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rc3_runtime_detail import RULES, tabulate  # noqa: E402

OPENING_TAG = re.compile(r"^<([a-zA-Z0-9-]+)[^>]*?(?:\sclass=\"([^\"]*)\")?[^>]*>")


def signature(html: str) -> str:
    match = OPENING_TAG.match(html)
    if not match:
        return html[:60]
    return f"{match.group(1)}.{' '.join(sorted((match.group(2) or '').split()))}"


def rule_row(summary: dict | None) -> dict:
    if not summary:
        return {"routes_failing": 0, "distinct_elements": 0, "style_signatures": 0}
    elements = summary["elements"]
    row = {
        "routes_failing": summary["routes_failing"],
        "distinct_elements": summary["distinct_elements"],
        "style_signatures": len({signature(element["html"]) for element in elements}),
    }
    if "colour_pairs" in summary:
        row["colour_pairs"] = len(summary["colour_pairs"])
    return row


def overflow(path: Path) -> dict:
    loads = json.loads(path.read_text())["observations"]
    wide = [row for row in loads if row.get("horizontal_overflow_px", 0) > 0]
    by_width: dict[str, list] = {}
    for row in wide:
        by_width.setdefault(str(row["width"]), []).append(row["route"])
    return {
        "routes": len({row["route"] for row in wide}),
        "page_loads_by_width": {
            width: len(routes) for width, routes in sorted(by_width.items(), key=lambda i: int(i[0]))
        },
        "routes_by_width": {
            width: sorted(routes) for width, routes in sorted(by_width.items(), key=lambda i: int(i[0]))
        },
    }


def reachability(path: Path) -> dict:
    loads = json.loads(path.read_text())["observations"]
    by_route: dict[str, list] = {}
    for row in loads:
        by_route.setdefault(row["route"], []).append(row)
    not_ok = {}
    for route, rows in sorted(by_route.items()):
        reasons = sorted(
            {
                reason
                for row in rows
                for reason, bad in (
                    ("error", "error" in row),
                    ("status", row.get("status") != 200),
                    ("no_text", row.get("rendered_text_chars", 0) == 0),
                    ("not_found_text", bool(row.get("not_found_text"))),
                )
                if bad
            }
        )
        if reasons:
            not_ok[route] = reasons
    return {"routes": len(by_route), "page_loads": len(loads), "routes_with_a_problem": not_ok}


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("rc3", "rescan", "audited-raw", "rescan-commit", "drift", "pins", "out"):
        parser.add_argument(f"--{name}", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rc3 = json.loads(Path(args.rc3).read_text())
    drift = json.loads(Path(args.drift).read_text())
    pins = json.loads(Path(args.pins).read_text())
    before = {app["repository"]: app for app in rc3["applications"]}

    rescan_path = Path(args.rescan) / "out-thehub-pr.json"
    after = tabulate(rescan_path)
    comparison = {
        rule: {
            "audited_commit": rule_row(before["thehub-pr"]["rules"].get(rule)),
            "rescanned_commit": rule_row(after["rules"].get(rule)),
        }
        for rule in RULES
    }
    rescan = {
        "schema": "federation.experience-program.rescan/1",
        "repository": "thehub-pr",
        "audited_commit": drift["thehub-pr"]["audited"],
        "rescanned_commit": args.rescan_commit,
        "method": rc3["method"],
        "reachability": reachability(rescan_path),
        "horizontal_overflow": {
            "audited_commit": overflow(Path(args.audited_raw)),
            "rescanned_commit": overflow(rescan_path),
        },
        "by_rule": comparison,
        "rescanned_detail": after,
    }
    (out / "thehub_rescan.json").write_text(json.dumps(rescan, indent=1, ensure_ascii=False) + "\n")

    rows = []
    for name, app in sorted(before.items()):
        current = name == "thehub-pr"
        source = after if current else app
        moved = drift[name]["frontend_change"] != "none"
        rows.append(
            {
                "repository": name,
                "routes": source["routes"],
                "page_loads": source["page_loads"],
                "evidence_commit": args.rescan_commit if current else drift[name]["audited"],
                "evidence_is_current_main": current or not moved,
                "frontend_changed_on_main_since_evidence": "none"
                if current
                else drift[name]["frontend_change"],
                "design_system_pin": pins[name],
                "by_rule": {rule: rule_row(source["rules"].get(rule)) for rule in RULES},
                "distinct_failing_elements": sum(
                    source["rules"].get(rule, {}).get("distinct_elements", 0) for rule in RULES
                ),
            }
        )
    document = {
        "schema": "federation.experience-program.rc4-plan-input/1",
        "claim_class": "COMPUTED",
        "note": (
            "Counts are distinct failing elements for four axe rules in Chromium, pages loaded and not "
            "operated. An application with one addressable route was scanned on that route only, so a low "
            "count there is a statement about coverage, not about the application."
        ),
        "applications": rows,
    }
    (out / "RC4_PLAN_INPUT.json").write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n")
    for row in rows:
        print(
            row["repository"],
            row["routes"],
            row["distinct_failing_elements"],
            {
                rule: (value["distinct_elements"], value["style_signatures"])
                for rule, value in row["by_rule"].items()
            },
        )


if __name__ == "__main__":
    main()
