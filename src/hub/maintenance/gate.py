"""Federation promotion gate for the maintenance rollup.

Pure policy over an aggregated rollup dict. The gate blocks promotion when:
  - any producer maintenance report is missing,
  - any producer report failed schema validation,
  - any producer declares its own gate blocked, or
  - any producer reports one or more critical findings.

This mirrors the workbook Gate Policy: missing producer report, invalid report
schema, and any critical finding are all federation-level blockers.
"""
from __future__ import annotations

from typing import Any, Dict, List


def compute_gate(rollup: Dict[str, Any]) -> Dict[str, Any]:
    """Return {"promotion_blocked": bool, "blockers": [str, ...]} for a rollup."""
    blockers: List[str] = []

    missing = int(rollup.get("reports_missing", 0))
    if missing:
        blockers.append(f"{missing} producer maintenance report(s) missing")

    invalid = int(rollup.get("reports_invalid", 0))
    if invalid:
        blockers.append(f"{invalid} producer maintenance report(s) failed schema validation")

    for repo, status in sorted(rollup.get("repo_status", {}).items()):
        critical = int(status.get("critical_count", 0))
        if critical:
            blockers.append(f"{repo}: {critical} critical finding(s)")
        if status.get("promotion_blocked"):
            blockers.append(f"{repo}: producer gate reports promotion_blocked")

    return {"promotion_blocked": bool(blockers), "blockers": blockers}
