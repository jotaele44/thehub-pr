"""Deterministic, audit-first maintenance/audit layer shared across PRII producer repos.

The shared module set — models, state, detect, corrections, quarantine,
report, runner — is generic; each producer keeps its own repo-specific checks
vendored locally (e.g. ``maintenance/adapters/local.py``) and passes them into
``run_maintenance(..., local_checks=...)``.
"""

from __future__ import annotations

from .models import MAINTENANCE_VERSION, MaintenanceFinding, MaintenanceReport
from .report import REPORT_RELPATH
from .runner import run_maintenance

__all__ = [
    "MAINTENANCE_VERSION",
    "MaintenanceFinding",
    "MaintenanceReport",
    "REPORT_RELPATH",
    "run_maintenance",
]
