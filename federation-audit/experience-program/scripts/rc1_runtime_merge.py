#!/usr/bin/env python3
"""Merge the Chromium runtime pass into RC1 artifacts.

Input is one ``out-<repo>.json`` per application, written by
``scripts/runtime/chromium_pass.js`` while that application ran on its real
backend. This script only tabulates. A route counts as OBSERVED_RUNTIME when it
answered 200, stayed on the address asked for, rendered text, and did not show a
not-found page, at every width tried.

Usage:
  rc1_runtime_merge.py --observations <dir> --surveys <dir> --out <dir>
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPOS = (
    "aguayluz-pr", "centinelas-pr", "moneysweep-pr", "mucaro-ai",
    "ovnis-pr", "skywatcher-pr", "spiderweb-pr", "thehub-pr",
)
WIDTHS = (320, 390, 430, 768, 1280, 1440, 1920)
BLOCKING = ("critical", "serious")


def same_address(row: dict) -> bool:
    """True when the page stayed where it was sent.

    A route asked for without a query string may add its own default parameters
    (``/constellation`` becomes ``/constellation?lens=...``); that is the same
    page. A change of path is a redirect and is not.
    """
    route, final = row.get("route") or "", row.get("final_path") or ""
    return final == route or ("?" not in route and final.split("?", 1)[0] == route)


def observed(row: dict) -> bool:
    return (
        row.get("status") == 200
        and not row.get("error")
        and same_address(row)
        and (row.get("rendered_text_chars") or 0) >= 40
        and not row.get("not_found_text")
        and not row.get("page_errors")
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--surveys", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    applications, findings = {}, []
    for name in REPOS:
        path = args.observations / f"out-{name}.json"
        if not path.is_file():
            applications[name] = {"state": "OPEN", "reason": "no runtime observations"}
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data["observations"]
        survey = json.loads((args.surveys / f"{name}.json").read_text(encoding="utf-8"))
        by_route: dict[str, list[dict]] = {}
        for row in rows:
            by_route.setdefault(row["route"], []).append(row)

        routes = {}
        for route, group in by_route.items():
            seen = all(observed(row) for row in group) and len(group) == len(WIDTHS)
            axe = Counter()
            for row in group:
                for violation in row.get("axe") or []:
                    if violation["impact"] in BLOCKING:
                        axe[violation["id"]] = max(axe[violation["id"]], violation["nodes"])
            overflow = sorted({row["width"] for row in group if (row.get("horizontal_overflow_px") or 0) > 1})
            redirected = sorted({row.get("final_path") for row in group
                                 if row.get("final_path") and not same_address(row)})
            normalised = sorted({row.get("final_path") for row in group
                                 if same_address(row) and row.get("final_path") != route})
            routes[route] = {
                "classification": "OBSERVED_RUNTIME" if seen else "SOURCE_CONFIRMED",
                "widths_observed": sorted(row["width"] for row in group if observed(row)),
                "redirected_to": redirected,
                "address_normalised_to": normalised,
                "errors": sorted({row["error"] for row in group if row.get("error")})[:2],
                "page_errors": sorted({e for row in group for e in row.get("page_errors") or []})[:2],
                "failed_requests": sorted({r for row in group for r in row.get("failed_requests") or []})[:6],
                "console_error_rows": sum(1 for row in group if row.get("console_errors")),
                "horizontal_overflow_at_widths": overflow,
                "max_horizontal_overflow_px": max((row.get("horizontal_overflow_px") or 0) for row in group),
                "missing_main_landmark_at_widths": sorted(
                    row["width"] for row in group if row.get("has_main_landmark") is False),
                "max_controls_under_24px": max((row.get("controls_under_24px") or 0) for row in group),
                "max_unnamed_buttons": max((row.get("unnamed_buttons") or 0) for row in group),
                "axe_blocking": dict(sorted(axe.items())),
            }
            for rule, nodes in sorted(axe.items()):
                findings.append({"repository": name, "route": route, "kind": "axe", "rule": rule,
                                 "max_nodes": nodes, "evidence_class": "OBSERVED_RUNTIME"})
            if overflow:
                findings.append({"repository": name, "route": route, "kind": "horizontal-overflow",
                                 "widths": overflow, "max_px": routes[route]["max_horizontal_overflow_px"],
                                 "evidence_class": "OBSERVED_RUNTIME"})
            if routes[route]["max_unnamed_buttons"]:
                findings.append({"repository": name, "route": route, "kind": "unnamed-button",
                                 "max_count": routes[route]["max_unnamed_buttons"],
                                 "evidence_class": "OBSERVED_RUNTIME"})

        mounted = [s for s in survey["surfaces"] if s.get("mounted") is True]
        addressable = {
            s["address"] for s in mounted
            if isinstance(s.get("address"), str) and s["address"].startswith("/")
            and ":" not in s["address"] and "*" not in s["address"] and " " not in s["address"]
        }
        seen_routes = {r for r, v in routes.items() if v["classification"] == "OBSERVED_RUNTIME"}
        applications[name] = {
            "state": "PROVISIONAL",
            "axe_version": data.get("axe_version"),
            "csp_bypassed_for_scan": bool(data.get("csp_bypassed_for_scan")),
            "router": survey["frontend"].get("router"),
            "routes_tried": len(routes),
            "routes_observed_runtime": len(seen_routes),
            "routes_not_observed": sorted(set(routes) - seen_routes),
            "mounted_surfaces_in_survey": len(mounted),
            "mounted_surfaces_with_an_address": len(addressable),
            "mounted_surfaces_without_an_address": len(mounted) - sum(
                1 for s in mounted if s.get("address") in addressable),
            "routes_with_blocking_axe": sum(1 for v in routes.values() if v["axe_blocking"]),
            "routes_with_horizontal_overflow": sum(
                1 for v in routes.values() if v["horizontal_overflow_at_widths"]),
            "routes": routes,
        }

    args.out.mkdir(parents=True, exist_ok=True)
    present = [a for a in applications.values() if a["state"] != "OPEN"]
    payload = {
        "schema": "federation.experience-program.runtime-observations/1",
        "generated_at": generated,
        "evidence_class": "OBSERVED_RUNTIME for the rows it lists, in one browser only.",
        "environment": {
            "browser": "Chromium (Playwright), headless, dark colour scheme",
            "os": "Linux container",
            "viewport_widths_css_px": list(WIDTHS),
            "backend": "each application's real backend at its RC0 commit, with a fresh "
                       "temporary workspace seeded by the application's own setup action",
            "desktop_runtime": "served through prii_desktop from the hub checkout, not the "
                               "version each producer pins",
        },
        "limits": [
            "Chromium only. Firefox and WebKit were not available.",
            (
                "Only surfaces with their own address were visited. Dialogs, drawers, tabs "
                "held in memory and anything behind a click were not opened."
            ),
            "Pages were loaded, not operated: no form was submitted and no write was attempted.",
            (
                "An axe scan finds a subset of accessibility failures. It is not a keyboard "
                "or screen-reader review."
            ),
            "Data was whatever a fresh workspace holds, so empty and loaded states are mixed.",
        ],
        "totals": {
            "applications_run": len(present),
            "routes_tried": sum(a["routes_tried"] for a in present),
            "routes_observed_runtime": sum(a["routes_observed_runtime"] for a in present),
            "routes_with_blocking_axe": sum(a["routes_with_blocking_axe"] for a in present),
            "routes_with_horizontal_overflow": sum(a["routes_with_horizontal_overflow"] for a in present),
            "page_loads": sum(a["routes_tried"] for a in present) * len(WIDTHS),
        },
        "applications": applications,
    }
    (args.out / "runtime_observations.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    (args.out / "runtime_findings.json").write_text(json.dumps({
        "schema": "federation.experience-program.runtime-findings/1",
        "generated_at": generated,
        "note": "Observed in Chromium on a fresh workspace. axe rows are critical or serious "
                "only; max_nodes is the largest node count seen at any width.",
        "findings": findings,
    }, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"totals": payload["totals"], "per_app": {
        k: (v.get("routes_observed_runtime"), v.get("routes_tried")) for k, v in applications.items()}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
