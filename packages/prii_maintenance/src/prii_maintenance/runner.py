"""Audit-first maintenance orchestration, shared across PRII producer repos.

collect state -> generic detectors -> repo-supplied adapter checks -> report.
Auto-correction only runs in explicit ``safe-correct`` mode.

Each producer keeps its own repo-specific checks vendored locally (e.g.
``maintenance/adapters/local.py``) and passes them in via ``local_checks`` —
this package intentionally has no adapters of its own, since those checks are
genuinely repo-specific and not shareable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

from . import corrections, detect
from . import state as state_mod
from .models import MaintenanceFinding, MaintenanceReport
from .quarantine import write_review_queue
from .report import write_latest_report

VALID_MODES = ("audit", "safe-correct")
LocalChecks = Callable[[str, Path, dict], Sequence[MaintenanceFinding]]


def _no_local_checks(repo: str, root: Path, state: dict) -> list[MaintenanceFinding]:
    return []


def run_maintenance(
    root: str | Path,
    mode: str = "audit",
    write: bool = True,
    program_id: str | None = None,
    local_checks: LocalChecks = _no_local_checks,
) -> MaintenanceReport:
    if mode not in VALID_MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {VALID_MODES}")
    root_path = Path(root)
    state = state_mod.collect_repo_state(root_path)
    repo = state["federation"].get("program_id") or program_id
    if not repo:
        raise ValueError(
            "no program id: federation.json has no program_id and none was "
            "passed via program_id="
        )

    findings: list[MaintenanceFinding] = []
    findings += detect.detect_missing_required_files(repo, root_path, state)
    findings += detect.detect_invalid_json(repo, root_path, state)
    findings += detect.detect_exact_duplicate_jsonl(repo, root_path, state)
    findings += list(local_checks(repo, root_path, state))

    if mode == "safe-correct":
        for finding in corrections.plan_safe_corrections(findings):
            if not finding.path:
                continue
            removed = corrections.remove_exact_duplicate_jsonl_rows(
                root_path / finding.path
            )
            if removed:
                finding.action = "auto_corrected"
                finding.detail = {**(finding.detail or {}), "rows_removed": removed}

    report = MaintenanceReport(repo=repo, findings=findings, mode=mode)
    if write:
        write_latest_report(report, root_path)
        write_review_queue(repo, findings, root_path)
    return report
