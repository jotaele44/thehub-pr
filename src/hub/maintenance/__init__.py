"""Hub-side federation maintenance: load producer reports, roll up, gate.

The maintenance layer is audit-first. Producers emit a deterministic
``reports/maintenance/latest.json`` (conforming to ``maintenance_report.schema.json``);
the Hub aggregates them and computes a promotion gate that blocks federation
readiness when any producer report is missing/invalid or any critical finding exists.
"""
from __future__ import annotations

from .gate import compute_gate
from .rollup import MAINTENANCE_VERSION, REPORT_RELPATH, build_rollup, validate_report

__all__ = [
    "MAINTENANCE_VERSION",
    "REPORT_RELPATH",
    "build_rollup",
    "validate_report",
    "compute_gate",
]
