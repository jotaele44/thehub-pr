#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CENSUS = ROOT / "audit" / "generated" / "federation_gui_census" / "census.json"
RUNTIME = ROOT / "audit" / "federation_gui_runtime_evidence.json"
CONTRACT = ROOT / "audit" / "federation_gui_regression_contract.json"
OUT = ROOT / "audit" / "generated" / "federation_gui_census" / "certification_arithmetic.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    census = load(CENSUS)
    runtime = load(RUNTIME)
    contract = load(CONTRACT)

    surfaces = int(census["totals"]["routes"]) + int(census["totals"]["workbench_modules"])
    browsers = len(contract["required_browser_engines"])
    viewports = len(contract["required_viewports"])
    a11y_modes = len(contract["required_accessibility_modes"])
    positive = len(contract["positive_fixtures"])
    negative = len(contract["negative_fixtures"])

    screenshot_denominator = surfaces * browsers * viewports
    accessibility_denominator = surfaces * a11y_modes
    declared_fixture_denominator = positive + negative

    missing_browser_harnesses = sorted(
        repo for repo, evidence in runtime["repositories"].items()
        if evidence.get("browser_harness") == "OPEN"
    )

    evidenced_screenshots = int(runtime["browser_matrix"].get("evidenced_screenshot_cells", 0))
    evidenced_a11y = int(runtime["accessibility"].get("evidenced_cells", 0))
    fixtures_closed = bool(
        runtime["regression"].get("all_positive_fixtures_runtime_executed")
        and runtime["regression"].get("all_negative_fixtures_runtime_executed")
    )

    arithmetic = {
        "snapshot_label": census["snapshot_label"],
        "repositories_expected": census["repositories_expected"],
        "repositories_censused": census["repositories_censused"],
        "snapshot_mismatches": len(census.get("snapshot_mismatches", [])),
        "top_level_navigation_surfaces": surfaces,
        "required_browser_engines": browsers,
        "required_viewports": viewports,
        "required_accessibility_modes": a11y_modes,
        "declared_positive_fixtures": positive,
        "declared_negative_fixtures": negative,
        "declared_fixture_denominator": declared_fixture_denominator,
        "screenshot_denominator": screenshot_denominator,
        "screenshot_evidenced": evidenced_screenshots,
        "screenshot_residue": max(0, screenshot_denominator - evidenced_screenshots),
        "accessibility_denominator": accessibility_denominator,
        "accessibility_evidenced": evidenced_a11y,
        "accessibility_residue": max(0, accessibility_denominator - evidenced_a11y),
        "missing_browser_harness_repositories": missing_browser_harnesses,
        "unassessed_ui_surfaces": surfaces if not runtime["browser_matrix"].get("full_surface_matrix_executed") else 0,
        "unresolved_scope_items": len(missing_browser_harnesses) + (0 if fixtures_closed else 1),
        "p0_open": int(runtime["findings"].get("p0_open", 0)),
        "p1_unadjudicated": int(runtime["findings"].get("p1_unadjudicated", 0)),
        "positive_and_negative_runtime_fixtures_closed": fixtures_closed,
    }

    pass_gate = all([
        arithmetic["repositories_expected"] == arithmetic["repositories_censused"],
        arithmetic["snapshot_mismatches"] == 0,
        arithmetic["unassessed_ui_surfaces"] == 0,
        arithmetic["unresolved_scope_items"] == 0,
        arithmetic["p0_open"] == 0,
        arithmetic["p1_unadjudicated"] == 0,
        arithmetic["screenshot_residue"] == 0,
        arithmetic["accessibility_residue"] == 0,
        arithmetic["positive_and_negative_runtime_fixtures_closed"],
    ])
    arithmetic["certification"] = "PASS" if pass_gate else "OPEN"
    arithmetic["unexplained_residue"] = 0 if pass_gate else (
        arithmetic["screenshot_residue"]
        + arithmetic["accessibility_residue"]
        + arithmetic["unresolved_scope_items"]
        + arithmetic["p1_unadjudicated"]
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(arithmetic, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(arithmetic, indent=2, sort_keys=True))
    return 0 if pass_gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
