#!/usr/bin/env python3
"""Build a committable snapshot of each producer's GUI-capability-parity gate.

Why this exists
----------------
``docs/FEDERATION_ROAD_TO_100_SCORECARD.v1.json`` carries a self-scored
``gui_completeness`` dimension per repo. A 2026-08-20 reassessment of every
producer's ``.federation/gui-capabilities.json`` /
``scripts/check_gui_parity.py`` found that three of six producers
(ovnis-pr, skywatcher-pr, spiderweb-pr) have no such gate on ``main`` at
all, and two more (aguayluz-pr, centinelas-pr) pass today but only because
real gaps are quietly carried in a legacy-debt baseline. None of that was
visible from the scorecard's self-scored number.

This is the moneysweep-pr fix's counterpart at the federation level: rather
than trust a subjective score, run each producer's own parity checker where
one exists on ``main``, and commit the real numbers. It intentionally does
**not** rewrite ``FEDERATION_ROAD_TO_100_SCORECARD.v1.json`` — that document
is a hand-audited governance ledger with narrative score-change
justifications per entry, and mechanically overwriting it would break that
audit trail. This script produces the derived evidence the next audit can
cite instead.

Mirrors scripts/build_federation_status.py's contract: filesystem-local, run
in a workspace holding the producer checkouts side by side (this one also
shells out to each producer's own checker script — a deployed hub has none
of the checkouts and cannot recompute this any more than it could
`hub validate-federation`). Point-in-time snapshot, not a live feed — it
carries ``generated_at`` for the same reason ``data/federation_status.json``
does.

Usage:
    python3 scripts/build_gui_parity_status.py --root .. --out data
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hub.gui_parity_status import ProducerGuiParity, classify, summarize  # noqa: E402
from hub.registry import Producer, load_registry  # noqa: E402

_CHECKER_TIMEOUT_SECONDS = 180


def _producer_base(root: Path, producer: Producer) -> Path:
    if producer.local_path:
        return root / producer.local_path
    return root / producer.repo_name


def _staged_capability_count(manifest_path: Path) -> int:
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError):
        return 0
    return sum(
        1
        for capability in manifest.get("capabilities", [])
        if isinstance(capability, dict) and capability.get("status") == "staged"
    )


def _run_checker(base: Path) -> Tuple[Optional[dict], Optional[str]]:
    """Run a producer's own scripts/check_gui_parity.py; return (report, error).

    Runs with the producer's checkout as both cwd and --repo-root, exactly
    how its own CI invokes it, so this reads the same manifest/baseline the
    producer's real gate reads — not a copy or a re-implementation of the
    check's logic.
    """
    checker = base / "scripts" / "check_gui_parity.py"
    with tempfile.TemporaryDirectory() as tmp:
        report_path = Path(tmp) / "report.json"
        try:
            subprocess.run(
                [
                    sys.executable,
                    str(checker),
                    "--report",
                    str(report_path),
                    "--repo-root",
                    str(base),
                ],
                cwd=base,
                capture_output=True,
                text=True,
                timeout=_CHECKER_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return None, f"{type(exc).__name__}: {exc}"
        if not report_path.exists():
            return None, "checker exited without writing a report"
        try:
            return json.loads(report_path.read_text()), None
        except json.JSONDecodeError as exc:
            return None, f"unparseable report: {exc}"


def build(registry_path: Path, root: Path, generated_at: str) -> dict:
    registry = load_registry(str(registry_path))
    rows: list[ProducerGuiParity] = []

    for producer in registry.producers:
        base = _producer_base(root, producer)
        checkout_present = base.exists()
        gui_manifest_path = base / ".federation" / "gui-capabilities.json"
        gui_checker_path = base / "scripts" / "check_gui_parity.py"
        gui_manifest_present = checkout_present and gui_manifest_path.exists()
        gui_checker_present = checkout_present and gui_checker_path.exists()

        staged_count = (
            _staged_capability_count(gui_manifest_path) if gui_manifest_present else 0
        )

        mode = current = mapped = legacy = new = manifest_issues = passed = None
        run_error = None
        if gui_manifest_present and gui_checker_present:
            report, run_error = _run_checker(base)
            if report is not None:
                summary = report.get("summary", {})
                mode = report.get("mode")
                passed = report.get("passed")
                current = summary.get("current_candidates")
                mapped = summary.get("mapped_candidates")
                legacy = summary.get("legacy_gaps")
                new = summary.get("new_gaps")
                manifest_issues = summary.get("manifest_issues")

        blocker_class = classify(
            checkout_present=checkout_present,
            gui_manifest_present=gui_manifest_present,
            gui_checker_present=gui_checker_present,
            run_error=run_error,
            passed=passed,
            new=new,
            manifest_issues=manifest_issues,
            staged_capability_count=staged_count,
        )

        rows.append(
            ProducerGuiParity(
                program_id=producer.program_id,
                repo=producer.repo,
                local_path=(
                    base.relative_to(root).as_posix()
                    if checkout_present
                    else producer.repo_name
                ),
                checkout_present=checkout_present,
                gui_manifest_present=gui_manifest_present,
                gui_checker_present=gui_checker_present,
                staged_capability_count=staged_count,
                mode=mode,
                current=current,
                mapped=mapped,
                legacy=legacy,
                new=new,
                manifest_issues=manifest_issues,
                passed=passed,
                run_error=run_error,
                blocker_class=blocker_class,
            )
        )

    summary = summarize(rows)
    summary["kind"] = "gui-parity-snapshot"
    summary["hub"] = registry.hub
    summary["generated_at"] = generated_at
    summary["note"] = (
        "Built by scripts/build_gui_parity_status.py, running each producer's own "
        "scripts/check_gui_parity.py against a workspace holding the producer "
        "checkouts. Point-in-time snapshot, not live state: a deployed hub has no "
        "producer checkouts and cannot recompute this. Regenerate with "
        "`make gui-parity-status`. Feeds the gui_completeness dimension of the "
        "next FEDERATION_ROAD_TO_100_SCORECARD audit; does not replace it."
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT.parent,
        help="workspace holding the producer checkouts",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "data",
        help="destination directory for gui_parity_status.json",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=REPO_ROOT / "registry" / "producers.yaml",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    generated_at = datetime.now(timezone.utc).isoformat()
    summary = build(args.registry, root, generated_at)

    args.out.mkdir(parents=True, exist_ok=True)
    destination = args.out / "gui_parity_status.json"
    destination.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(f"gui parity status written to {destination}")
    print(
        f"  {summary['producer_count']} producers, {summary['clean_count']} clean, "
        f"blockers: {summary['by_blocker']}"
    )
    no_gate = [
        p["program_id"]
        for p in summary["producers"]
        if p["blocker_class"] == "no_gui_parity_gate"
    ]
    if no_gate:
        print(f"  NOTE: no GUI-parity gate at all on main for: {', '.join(no_gate)}")
    missing = [
        p["program_id"] for p in summary["producers"] if not p["checkout_present"]
    ]
    if missing:
        print(
            f"  WARNING: no checkout found for {', '.join(missing)} — "
            f"rerun with --root pointing at the producer workspace"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
