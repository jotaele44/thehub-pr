#!/usr/bin/env python3
"""Merge the eight RC1 application surveys into the program's inventory artifacts.

Each survey is one JSON file per repository, produced from a read-only snapshot
of that repository at its RC0 commit. This script does not audit anything. It
checks each survey's shape and internal consistency, verifies that every
``path:line`` citation points at a line that exists in the audited snapshot, and
writes the merged artifacts. A survey that fails validation is reported, not
repaired.

Usage:
  rc1_merge.py --surveys <dir> --snapshots <dir> --baselines <rc0/repository_baselines.json> --out <dir>
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPOS = (
    "aguayluz-pr", "centinelas-pr", "moneysweep-pr", "mucaro-ai",
    "ovnis-pr", "skywatcher-pr", "spiderweb-pr", "thehub-pr",
)
REQUIRED = (
    "repository", "audited_commit", "frontend", "entry_points", "surfaces",
    "workflows", "navigation", "settings", "context_actions", "keyboard_shortcuts",
    "accessibility_source_findings", "backend", "tests", "performance_protections",
    "special_adjudications", "denominator", "unknowns",
)
SURFACE_CLASSES = {"SOURCE_CONFIRMED", "MANIFEST_DECLARED", "HISTORICAL_ONLY", "UNKNOWN"}
WORKFLOW_STATES = {"COMPLETE", "PARTIAL", "BROKEN", "UNREACHABLE", "INTERNAL_ONLY"}
SETTING_SCOPES = {
    "GLOBAL_USER", "APPLICATION_USER", "WORKSPACE", "SESSION", "ADMINISTRATIVE", "SECRET",
}
ADJUDICATION_STATES = {
    "CONFIRMED_PRESENT", "CONFIRMED_FIXED", "PARTIAL", "NOT_FOUND", "UNKNOWN",
}
# A citation is "<path>.<ext>:<line>". Path characters exclude whitespace and
# brackets so surrounding prose is not swallowed; a path containing a space is
# therefore under-captured and reported as unresolved rather than guessed.
CITATION = re.compile(r"(?<![\w./@+-])((?:[\w.@+-]+/)*[\w.@+-]+\.[A-Za-z0-9]+):(\d+)(?![\d.])")


def citations(value) -> list[tuple[str, int]]:
    """Every path:line found anywhere inside a JSON value."""
    found: list[tuple[str, int]] = []
    if isinstance(value, str):
        found.extend((m.group(1).strip(), int(m.group(2))) for m in CITATION.finditer(value))
    elif isinstance(value, dict):
        for item in value.values():
            found.extend(citations(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(citations(item))
    return found


def check_citations(survey: dict, snapshot: Path) -> dict:
    line_counts: dict[str, int | None] = {}
    total = missing_file = bad_line = by_basename = 0
    samples: list[str] = []
    # A citation written as a bare file name ("App.jsx:60") is accepted only
    # when exactly one tracked file has that name; otherwise it stays unresolved.
    by_name: dict[str, list[str]] = {}
    for file in snapshot.rglob("*"):
        if file.is_file() and "node_modules" not in file.parts:
            by_name.setdefault(file.name, []).append(file.relative_to(snapshot).as_posix())
    for cited, line in citations(survey):
        total += 1
        path = cited
        if not (snapshot / cited).is_file():
            matches = [m for m in by_name.get(cited.rsplit("/", 1)[-1], [])
                       if m == cited or m.endswith("/" + cited)]
            if len(matches) == 1:
                path = matches[0]
                by_basename += 1
        if path not in line_counts:
            target = snapshot / path
            try:
                line_counts[path] = (
                    sum(1 for _ in target.open("rb")) if target.is_file() else None
                )
            except OSError:
                line_counts[path] = None
        count = line_counts[path]
        if count is None:
            missing_file += 1
            if len(samples) < 8:
                samples.append(f"{path}:{line} (no such file)")
        elif not 1 <= line <= max(count, 1):
            bad_line += 1
            if len(samples) < 8:
                samples.append(f"{path}:{line} (file has {count} lines)")
    resolved = total - missing_file - bad_line
    return {
        "citations": total,
        "resolved": resolved,
        "resolved_via_unique_file_name": by_basename,
        "file_not_in_snapshot": missing_file,
        "line_out_of_range": bad_line,
        "resolved_ratio": round(resolved / total, 4) if total else None,
        "unresolved_samples": samples,
        "note": "Resolved means the cited file exists at the audited commit and has "
                "that line. It does not prove the line says what the survey claims.",
    }


def validate(name: str, survey: dict, commit: str) -> list[str]:
    problems = [f"missing key: {key}" for key in REQUIRED if key not in survey]
    if problems:
        return problems
    if survey["repository"] != name:
        problems.append(f"repository is {survey['repository']!r}")
    if survey["audited_commit"] != commit:
        problems.append(f"audited_commit {survey['audited_commit']!r} is not the RC0 commit")
    ids = [s.get("id") for s in survey["surfaces"]]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        problems.append(f"duplicate surface ids: {duplicates[:5]}")
    for surface in survey["surfaces"]:
        if surface.get("classification") not in SURFACE_CLASSES:
            problems.append(f"surface {surface.get('id')}: bad classification")
        if surface.get("mounted") and not surface.get("mounted_evidence"):
            problems.append(f"surface {surface.get('id')}: mounted without evidence")
        parent = surface.get("parent")
        if parent and parent not in ids:
            problems.append(f"surface {surface.get('id')}: unknown parent {parent!r}")
    workflow_ids = [w.get("id") for w in survey["workflows"]]
    duplicates = sorted({i for i in workflow_ids if workflow_ids.count(i) > 1})
    if duplicates:
        problems.append(f"duplicate workflow ids: {duplicates[:5]}")
    for workflow in survey["workflows"]:
        if workflow.get("status") not in WORKFLOW_STATES:
            problems.append(f"workflow {workflow.get('id')}: bad status {workflow.get('status')!r}")
        surface = workflow.get("surface")
        # A workflow nobody can reach from the UI legitimately has no surface.
        surfaceless_ok = workflow.get("status") in {"UNREACHABLE", "INTERNAL_ONLY", "BROKEN"}
        if surface not in ids and not (surface is None and surfaceless_ok):
            problems.append(f"workflow {workflow.get('id')}: unknown surface {surface!r}")
        if not workflow.get("status_evidence"):
            problems.append(f"workflow {workflow.get('id')}: status without evidence")
    for setting in survey["settings"]:
        if setting.get("scope") not in SETTING_SCOPES:
            problems.append(f"setting {setting.get('id')}: bad scope {setting.get('scope')!r}")
    for item in survey["special_adjudications"]:
        if item.get("status") not in ADJUDICATION_STATES:
            problems.append(f"adjudication status {item.get('status')!r}")
        if item.get("status", "").startswith("CONFIRMED") and not item.get("evidence"):
            problems.append("adjudication confirmed without evidence")
    return problems


def recount(survey: dict) -> dict:
    """The denominator recomputed from the rows, to compare with the survey's own."""
    by_status = {state: 0 for state in sorted(WORKFLOW_STATES)}
    for workflow in survey["workflows"]:
        if workflow.get("status") in by_status:
            by_status[workflow["status"]] += 1
    return {
        "surfaces_total": len(survey["surfaces"]),
        "surfaces_mounted": sum(1 for s in survey["surfaces"] if s.get("mounted") is True),
        "workflows_total": len(survey["workflows"]),
        "by_workflow_status": by_status,
        "workflows_with_test": sum(1 for w in survey["workflows"] if w.get("has_test") is True),
        "workflows_that_write": sum(1 for w in survey["workflows"] if w.get("writes") is True),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--surveys", type=Path, required=True)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--snapshots", type=Path, required=True)
    parser.add_argument("--baselines", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    commits = {
        item["repository"].split("/")[1]: item["identities"]["current_remote_head"]
        for item in json.loads(args.baselines.read_text())["repositories"]
    }

    applications, report = [], {}
    for name in REPOS:
        path = args.surveys / f"{name}.json"
        entry = {"survey_present": path.is_file()}
        report[name] = entry
        if not path.is_file():
            entry["state"] = "OPEN"
            continue
        try:
            survey = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            entry.update(state="FAIL", problems=[f"invalid JSON: {exc}"])
            continue
        problems = validate(name, survey, commits[name])
        entry["problems"] = problems
        if any(p.startswith("missing key") for p in problems):
            entry["state"] = "FAIL"
            continue
        recomputed = recount(survey)
        stated = survey["denominator"]
        entry["denominator_recomputed"] = recomputed
        entry["denominator_matches_survey"] = all(
            stated.get(key) == recomputed[key]
            for key in ("surfaces_total", "surfaces_mounted", "workflows_total")
        )
        entry["citations"] = check_citations(survey, args.snapshots / name)
        ratio = entry["citations"]["resolved_ratio"]
        entry["state"] = (
            "FAIL" if problems
            else "PROVISIONAL" if ratio is not None and ratio >= 0.95
            else "UNRESOLVED"
        )
        survey["denominator_recomputed"] = recomputed
        applications.append(survey)

    def dump(name: str, payload) -> None:
        (args.out / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    header = {
        "generated_at": generated,
        "evidence_class": "SOURCE_CONFIRMED at best. Nothing in this file was observed "
                          "at runtime; no application was started for this inventory.",
        "audited_commits": commits,
    }
    dump("application_inventory.json", {
        "schema": "federation.experience-program.application-inventory/1", **header,
        "applications": applications,
    })
    dump("settings_inventory.json", {
        "schema": "federation.experience-program.settings-inventory/1", **header,
        "settings": [
            {"repository": app["repository"], **item}
            for app in applications for item in app["settings"]
        ],
    })
    dump("context_actions_inventory.json", {
        "schema": "federation.experience-program.context-actions-inventory/1", **header,
        "context_actions": [
            {"repository": app["repository"], **item}
            for app in applications for item in app["context_actions"]
        ],
        "keyboard_shortcuts": [
            {"repository": app["repository"], **item}
            for app in applications for item in app["keyboard_shortcuts"]
        ],
    })
    dump("accessibility_findings.json", {
        "schema": "federation.experience-program.accessibility-findings/1", **header,
        "method": "Source reading only. No axe scan, screen reader or device was used "
                  "for these rows; each is a lead to confirm at runtime.",
        "findings": [
            {"repository": app["repository"], **item}
            for app in applications for item in app["accessibility_source_findings"]
        ],
    })
    dump("special_adjudications.json", {
        "schema": "federation.experience-program.special-adjudications/1", **header,
        "adjudications": [
            {"repository": app["repository"], **item}
            for app in applications for item in app["special_adjudications"]
        ],
    })

    surfaces = {
        (app["repository"], s["id"]): s for app in applications for s in app["surfaces"]
    }
    with (args.out / "ui_workflow_matrix.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow([
            "repository", "surface_id", "surface_kind", "surface_label", "address",
            "surface_mounted", "surface_classification", "frontend_component",
            "workflow_id", "workflow_name", "ui_action", "frontend_handler",
            "backend_endpoint", "backend_handler", "writes", "authorization",
            "workflow_status", "has_test", "test", "status_evidence",
        ])
        for app in applications:
            covered = set()
            for workflow in app["workflows"]:
                surface = surfaces.get((app["repository"], workflow.get("surface")), {})
                covered.add(workflow.get("surface"))
                writer.writerow([
                    app["repository"], workflow.get("surface"), surface.get("kind"),
                    surface.get("label"), surface.get("address"), surface.get("mounted"),
                    surface.get("classification"), surface.get("component"),
                    workflow.get("id"), workflow.get("name"), workflow.get("ui_action"),
                    workflow.get("frontend_handler"), workflow.get("backend_endpoint"),
                    workflow.get("backend_handler"), workflow.get("writes"),
                    workflow.get("authorization"), workflow.get("status"),
                    workflow.get("has_test"), workflow.get("test"),
                    workflow.get("status_evidence"),
                ])
            # A surface with no workflow row still belongs in the denominator.
            for surface in app["surfaces"]:
                if surface["id"] not in covered:
                    writer.writerow([
                        app["repository"], surface["id"], surface.get("kind"),
                        surface.get("label"), surface.get("address"), surface.get("mounted"),
                        surface.get("classification"), surface.get("component"),
                        "", "", "", "", "", "", "", "", "", "", "", "",
                    ])

    states = [entry["state"] for entry in report.values()]
    totals = {
        key: sum(e.get("denominator_recomputed", {}).get(key, 0) for e in report.values())
        for key in ("surfaces_total", "surfaces_mounted", "workflows_total",
                    "workflows_with_test", "workflows_that_write")
    }
    dump("RC1_GATE.json", {
        "schema": "federation.experience-program.gate/1",
        "gate": "RC1",
        "generated_at": generated,
        "state": (
            "OPEN" if "OPEN" in states else "FAIL" if "FAIL" in states
            else "UNRESOLVED" if "UNRESOLVED" in states else "PROVISIONAL"
        ),
        "why_not_pass": "The inventory is a source audit of eight commits. No surface was "
                        "observed at runtime, no survey row was independently re-checked "
                        "beyond citation resolution and a manual sample, and forms, "
                        "tables and filters inside pages are enumerated as stated in each "
                        "survey's coverage_statement, which may be sampled.",
        "totals": totals,
        "applications": report,
    })
    print(json.dumps({"state": json.loads((args.out / "RC1_GATE.json").read_text())["state"],
                      "totals": totals,
                      "per_app": {k: v["state"] for k, v in report.items()}}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
