#!/usr/bin/env python3
"""Performance baseline for the federation applications (RC8).

Three subcommands. The first two measure; the third tabulates. None of them
judges a number: no performance budget has been agreed.

  coldstart  Time from starting an application's backend to its first 200
             response, several runs, each on an empty temporary workspace
             (so each run includes the application's first-run setup).
  sizes      Raw and gzip size of a built frontend, split into what
             index.html loads up front and what is loaded later.
  tabulate   Combine those with the outputs of scripts/runtime/perf_pass.js
             into performance_baselines.json.

Timings come from the machine the scripts run on, over loopback. They compare
applications and commits with each other; they are not device timings.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SERVE = Path(__file__).resolve().parent / "runtime" / "serve_snapshot.py"
ASSET = re.compile(r"""(?:src|href)=["']([^"']+\.(?:js|css|mjs))["']""")
# A measure is quoted only if its runs agree this closely: (max - min) / median.
MAX_RELATIVE_SPREAD = 0.5
METRICS = ("ttfb_ms", "dom_content_loaded_ms", "load_ms", "lcp_ms", "cls", "requests", "transferred_bytes")


def summary(values: list[float]) -> dict:
    values = [value for value in values if value is not None]
    if not values:
        return {"runs": 0}
    median = statistics.median(values)
    spread = (max(values) - min(values)) / median if median else 0.0
    return {
        "runs": len(values),
        "median": round(median, 1),
        "min": round(min(values), 1),
        "max": round(max(values), 1),
        "relative_spread": round(spread, 3),
    }


def coldstart(args: argparse.Namespace) -> None:
    results = []
    for run in range(args.runs):
        started = time.monotonic()
        process = subprocess.Popen(
            [sys.executable, str(SERVE), args.snapshots, args.repository, str(args.port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        ready = None
        try:
            while time.monotonic() - started < args.timeout:
                if process.poll() is not None:
                    break
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{args.port}/", timeout=1) as response:
                        if response.status == 200:
                            ready = time.monotonic() - started
                            break
                except (urllib.error.URLError, ConnectionError, TimeoutError):
                    time.sleep(0.02)
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
        results.append(None if ready is None else round(ready * 1000, 1))
        print(args.label, "run", run, results[-1], flush=True)
        time.sleep(1)
    document = {
        "repository": args.repository,
        "label": args.label,
        "what": (
            "milliseconds from starting the backend process, on an empty workspace, "
            "to the first 200 response for /"
        ),
        "runs_ms": results,
        "failed_runs": sum(1 for value in results if value is None),
    }
    Path(args.out).write_text(json.dumps(document, indent=1) + "\n")


def sizes(args: argparse.Namespace) -> None:
    dist = Path(args.dist)
    index = (dist / "index.html").read_text()
    initial = {reference.split("?")[0].lstrip("./") for reference in ASSET.findall(index)}
    rows = []
    for path in sorted(dist.rglob("*")):
        if not path.is_file() or path.suffix not in (".js", ".css", ".mjs"):
            continue
        data = path.read_bytes()
        relative = path.relative_to(dist).as_posix()
        rows.append(
            {
                "file": relative,
                "kind": "css" if path.suffix == ".css" else "js",
                "initial": relative in initial,
                "raw_bytes": len(data),
                "gzip_bytes": len(gzip.compress(data, compresslevel=9, mtime=0)),
            }
        )

    def total(kind: str, initial_only: bool | None) -> dict:
        chosen = [
            row
            for row in rows
            if row["kind"] == kind and (initial_only is None or row["initial"] == initial_only)
        ]
        return {
            "files": len(chosen),
            "raw_bytes": sum(row["raw_bytes"] for row in chosen),
            "gzip_bytes": sum(row["gzip_bytes"] for row in chosen),
        }

    document = {
        "repository": args.repository,
        "label": args.label,
        "what": (
            "initial = referenced by index.html (script, stylesheet and modulepreload); "
            "later = every other built .js or .css file. gzip at level 9."
        ),
        "js": {"initial": total("js", True), "later": total("js", False), "all": total("js", None)},
        "css": {"initial": total("css", True), "later": total("css", False), "all": total("css", None)},
        "largest_files": sorted(rows, key=lambda row: -row["gzip_bytes"])[:5],
    }
    Path(args.out).write_text(json.dumps(document, indent=1) + "\n")
    print(args.label, document["js"]["initial"], document["js"]["all"])


def page_loads(path: Path) -> dict:
    data = json.loads(path.read_text())
    cells: dict[tuple, list] = {}
    for sample in data["samples"]:
        cells.setdefault((sample["route"], sample["width"]), []).append(sample)
    routes = []
    for (route, width), samples in sorted(cells.items()):
        good = [sample for sample in samples if "error" not in sample and sample.get("status") == 200]
        row = {"route": route, "width": width, "runs": len(samples), "failed_runs": len(samples) - len(good)}
        for metric in METRICS:
            row[metric] = summary([sample.get(metric) for sample in good])
        row["unreliable"] = sorted(
            metric
            for metric in ("dom_content_loaded_ms", "load_ms", "lcp_ms")
            if row[metric].get("relative_spread", 0) > MAX_RELATIVE_SPREAD
        )
        routes.append(row)

    def across(metric: str, width: int) -> dict:
        return summary(
            [row[metric]["median"] for row in routes if row["width"] == width and row[metric]["runs"]]
        )

    def top(metric: str) -> list:
        chosen = [row for row in routes if row["width"] == 1280 and row[metric]["runs"]]
        return [
            {
                "route": row["route"],
                "median": row[metric]["median"],
                "unreliable": metric in row["unreliable"],
            }
            for row in sorted(chosen, key=lambda row: -row[metric]["median"])[:5]
        ]

    return {
        "browser": data["browser"],
        "runs_per_cell": data["runs_per_cell"],
        "routes": len({row["route"] for row in routes}),
        "samples": len(data["samples"]),
        "failed_samples": sum(row["failed_runs"] for row in routes),
        "cells_with_an_unreliable_timing": sum(1 for row in routes if row["unreliable"]),
        "across_routes": {
            str(width): {metric: across(metric, width) for metric in METRICS} for width in data["widths"]
        },
        "slowest_routes_at_1280_by_lcp": top("lcp_ms"),
        "largest_routes_at_1280_by_bytes": top("transferred_bytes"),
        "by_route": routes,
    }


def tabulate(args: argparse.Namespace) -> None:
    source = Path(args.raw)
    targets = json.loads(Path(args.targets).read_text())
    applications = []
    for target in targets:
        label = target["label"]
        row = dict(target)
        cold = json.loads((source / f"coldstart-{label}.json").read_text())
        # The first start of a tree that has never run pays for compiling Python
        # bytecode and a cold file cache; later starts do not. They are different
        # quantities, so they are reported apart and never averaged together.
        row["cold_start_ms"] = {
            "first_run": cold["runs_ms"][0],
            "later_runs": summary(cold["runs_ms"][1:]),
            "failed_runs": cold["failed_runs"],
        }
        build = json.loads((source / f"sizes-{label}.json").read_text())
        row["build"] = {key: build[key] for key in ("js", "css", "largest_files")}
        row["page_load"] = page_loads(source / f"perf-{label}.json")
        applications.append(row)
    document = {
        "schema": "federation.experience-program.performance-baselines/1",
        "claim_class": "COMPUTED",
        "method": (
            "Each application's backend and built frontend, served by scripts/runtime/serve_snapshot.py. "
            "Cold start: 5 process starts, each on an empty temporary workspace, so each includes the "
            "application's own first-run setup. Page load: Chromium, dark colour scheme, every addressable "
            "route at 390 and 1280 CSS pixels, 3 runs per cell, a fresh browser context per run. Medians "
            "are reported with minimum, maximum and relative spread (max minus min, over median)."
        ),
        "limits": [
            "Measured in a Linux container over loopback. The numbers compare applications and commits with "
            "each other. They are not device timings and say nothing about macOS startup.",
            "Fresh workspaces hold little data, so data-heavy pages load faster here than in real use.",
            "Every cold-start run is on an empty workspace, so each includes the application's first-run "
            "setup. A start on an existing workspace was not measured.",
            "first_run is one observation per tree, not a distribution. For a tree that had never been run "
            "it includes compiling Python bytecode and reading files for the first time; "
            "tree_previously_run says which trees that applies to.",
            "Chromium only.",
            f"A timing whose runs differ by more than {int(MAX_RELATIVE_SPREAD * 100)}% of the median is "
            "listed as unreliable for that cell.",
            "No performance budget has been agreed. Nothing here is a pass or a failure.",
        ],
        "applications": applications,
    }
    Path(args.out).write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n")
    for row in applications:
        wide = row["page_load"]["across_routes"]["1280"]
        print(
            row["label"],
            "first start",
            row["cold_start_ms"]["first_run"],
            "later",
            row["cold_start_ms"]["later_runs"].get("median"),
            "js initial gz",
            row["build"]["js"]["initial"]["gzip_bytes"],
            "lcp",
            wide["lcp_ms"].get("median"),
            "bytes",
            wide["transferred_bytes"].get("median"),
            "unreliable cells",
            row["page_load"]["cells_with_an_unreliable_timing"],
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    cold = commands.add_parser("coldstart")
    for name in ("snapshots", "repository", "label", "out"):
        cold.add_argument(f"--{name}", required=True)
    cold.add_argument("--port", type=int, required=True)
    cold.add_argument("--runs", type=int, default=5)
    cold.add_argument("--timeout", type=float, default=90)
    cold.set_defaults(run=coldstart)
    size = commands.add_parser("sizes")
    for name in ("dist", "repository", "label", "out"):
        size.add_argument(f"--{name}", required=True)
    size.set_defaults(run=sizes)
    table = commands.add_parser("tabulate")
    for name in ("raw", "targets", "out"):
        table.add_argument(f"--{name}", required=True)
    table.set_defaults(run=tabulate)
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
