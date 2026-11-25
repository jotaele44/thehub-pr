#!/usr/bin/env python3
"""Tabulate a cross-engine runtime pass: the same build of each application
loaded in Chromium, Firefox and WebKit by ``runtime/chromium_pass.js`` or
``runtime/views_pass.js`` with ``GUI_ENGINE`` set.

Input is one directory per engine, each holding ``out-<repository>.json``.
For every application and engine it counts what was observed. It then lists
what an engine shows beyond Chromium on the same build: a critical or serious
axe rule on more page loads, a failing element Chromium did not report, more
page loads with horizontal overflow, page errors, or routes that did not
render. It decides nothing beyond that comparison.

A route counts as rendered (the RC1 rule) when, at every width, it answered
200, stayed on the address asked for, rendered text and showed no not-found
page. Routes that redirect by design are listed, not counted as failures.

Usage:
  rc10_engine_tabulate.py --raw <dir holding chromium/ firefox/ webkit/> \
      --commits <json: repository -> {commit, label}> --out <engine_matrix.json>
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ENGINES = ("chromium", "firefox", "webkit")
BLOCKING = ("critical", "serious")


def same_address(asked: str, final: str | None) -> bool:
    if final is None:
        return False
    if final == asked:
        return True
    # A route that adds its own default query parameters is the same page.
    return final.split("?")[0] == asked.split("?")[0] and "?" not in asked


def tabulate(out: dict) -> dict:
    rows = out["observations"]
    by_route: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_route[row["route"]].append(row)
    views = out.get("mode") == "in-memory views"
    rendered, redirected, not_rendered = [], [], []
    for route, rs in sorted(by_route.items()):
        if any(r.get("error") for r in rs):
            not_rendered.append(route)
            continue
        if views:
            ok = all((r.get("rendered_text_chars") or 0) > 0 for r in rs)
            (rendered if ok else not_rendered).append(route)
            continue
        if any(not same_address(route, r.get("final_path")) for r in rs):
            redirected.append(route)
            continue
        ok = all(r.get("status") == 200 and (r.get("rendered_text_chars") or 0) > 0 and not r.get("not_found_text") for r in rs)
        (rendered if ok else not_rendered).append(route)

    rule_loads: Counter = Counter()
    elements: dict[str, set] = defaultdict(set)
    for row in rows:
        for v in row.get("axe") or []:
            if v.get("impact") in BLOCKING:
                rule_loads[v["id"]] += 1
                for d in v.get("detail") or []:
                    elements[v["id"]].add(d.get("html", ""))
    overflow_by_width: Counter = Counter()
    for row in rows:
        if (row.get("horizontal_overflow_px") or 0) > 0:
            overflow_by_width[str(row["width"])] += 1
    return {
        "browser_version": out.get("browser_version"),
        "axe_version": out.get("axe_version"),
        "csp_bypassed_for_scan": out.get("csp_bypassed_for_scan", False),
        "mode": out.get("mode", "routes"),
        "page_loads": len(rows),
        "routes": len(by_route),
        "routes_rendered": len(rendered),
        "routes_redirected": redirected,
        "routes_not_rendered": not_rendered,
        "page_loads_with_an_error": sum(1 for r in rows if r.get("error")),
        "page_loads_with_page_errors": sum(1 for r in rows if r.get("page_errors")),
        "page_loads_with_console_errors": sum(1 for r in rows if r.get("console_errors")),
        "page_loads_with_horizontal_overflow": sum(overflow_by_width.values()),
        "horizontal_overflow_by_width": dict(sorted(overflow_by_width.items(), key=lambda kv: int(kv[0]))),
        "page_loads_with_an_unnamed_button": sum(1 for r in rows if (r.get("unnamed_buttons") or 0) > 0),
        "controls_under_24px_summed_over_page_loads": sum(r.get("controls_under_24px") or 0 for r in rows),
        "blocking_rules_page_loads": dict(sorted(rule_loads.items())),
        "detail_rules_distinct_elements": {k: len(v) for k, v in sorted(elements.items())},
        "_elements": {k: sorted(v) for k, v in elements.items()},
    }


def beyond_chromium(engine: dict, chromium: dict) -> list[str]:
    found = []
    for rule, n in engine["blocking_rules_page_loads"].items():
        base = chromium["blocking_rules_page_loads"].get(rule, 0)
        if n > base:
            found.append(f"{rule}: {n} page loads against {base} in Chromium")
    for rule, els in engine["_elements"].items():
        extra = sorted(set(els) - set(chromium["_elements"].get(rule, [])))
        if extra:
            found.append(f"{rule}: {len(extra)} element(s) Chromium did not report, e.g. {extra[0][:120]}")
    for key in ("page_loads_with_horizontal_overflow", "page_loads_with_page_errors", "page_loads_with_an_error", "page_loads_with_an_unnamed_button"):
        if engine[key] > chromium[key]:
            found.append(f"{key}: {engine[key]} against {chromium[key]} in Chromium")
    extra_nr = sorted(set(engine["routes_not_rendered"]) - set(chromium["routes_not_rendered"]))
    if extra_nr:
        found.append(f"routes not rendered only here: {extra_nr}")
    return found


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True, type=Path)
    ap.add_argument("--commits", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    commits = json.loads(a.commits.read_text())
    apps = {}
    for repo, meta in sorted(commits.items()):
        per = {}
        for engine in ENGINES:
            f = a.raw / engine / f"out-{repo}.json"
            if f.exists():
                per[engine] = tabulate(json.loads(f.read_text()))
        row = {"commit": meta["commit"], "commit_label": meta["label"], "claim_class": "COMPUTED", "engines": {}}
        for engine, t in per.items():
            entry = {k: v for k, v in t.items() if not k.startswith("_")}
            if engine != "chromium" and "chromium" in per:
                entry["beyond_chromium"] = beyond_chromium(t, per["chromium"])
            row["engines"][engine] = entry
        row["engines_missing"] = [e for e in ENGINES if e not in per]
        apps[repo] = row
    totals = {
        e: {
            "applications": sum(1 for r in apps.values() if e in r["engines"]),
            "page_loads": sum(r["engines"][e]["page_loads"] for r in apps.values() if e in r["engines"]),
            "applications_with_findings_beyond_chromium": sorted(
                k for k, r in apps.items() if e in r["engines"] and r["engines"][e].get("beyond_chromium")
            ) if e != "chromium" else None,
        }
        for e in ENGINES
    }
    doc = {
        "schema": "federation.experience-program.engine-matrix/1",
        "claim_classes": {"commit, browser_version": "FACT", "counts": "COMPUTED"},
        "method": "Each application's snapshot was built once and served on its own backend with a fresh temporary workspace. The same served build was loaded in Chromium, Firefox and WebKit (Playwright 1.63.0, Linux container, headless), dark colour scheme, at 320, 390, 430, 768, 1280, 1440 and 1920 CSS pixels, with axe-core 4.14.1. Pages and in-memory views were loaded or opened, not operated.",
        "rule": "A route is rendered when at every width it answered 200, stayed on its address, rendered text and showed no not-found page. 'beyond_chromium' lists what an engine shows that Chromium did not on the same build.",
        "applications": apps,
        "totals": totals,
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(totals, indent=1))


if __name__ == "__main__":
    main()
