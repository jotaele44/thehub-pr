"""Shared helpers for the ``source_monitors`` federation stream (ADR 0013).

Producers emit one row per monitored source, conforming to
``schemas/federation_source_monitor.schema.json`` in thehub-pr. The row says when
the source last succeeded and how that time is known:

* ``RUN_RECEIPT``: a producer fetch run recorded it in the committed
  ``data/source_run_state.json`` (see :class:`SourceRunState`);
* ``OUTPUT_DERIVED``: it was read from timestamps in the producer's own outputs;
* ``NOT_RECORDED``: neither exists, and ``last_success_at`` is null.

Nothing here infers a time from file modification dates or git history.
Stdlib only, so every producer can pin this package without new dependencies.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .helpers import fid

STATE_SCHEMA_VERSION = "prii_source_run_state_v1"
BASES = ("RUN_RECEIPT", "OUTPUT_DERIVED", "NOT_RECORDED")
DECLARED_STATUSES = ("active", "partial", "not_active", "manual", "inactive", "unknown")
CADENCES = (
    "realtime", "hourly", "daily", "weekly", "monthly", "quarterly", "yearly",
    "event", "static", "manual", "unknown",
)
ATTEMPT_STATUSES = ("success", "failure", "partial")
TIERS = ("T1", "T2", "T3", "T4")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse(ts: str) -> datetime:
    value = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def monitor_id(producer: str, source_ref: str) -> str:
    """Deterministic stream id: ``mon_`` + 32 hex, keyed on producer and registry id."""
    return fid("mon", producer, source_ref)


def resolve_last_success(
    state_row: Optional[Dict[str, Any]], derived_at: Optional[str],
) -> Tuple[Optional[str], str]:
    """Pick ``(last_success_at, basis)`` from a run receipt and an output-derived time.

    The more recent of the two wins; a tie goes to the run receipt. With neither,
    the result is ``(None, "NOT_RECORDED")``.
    """
    receipt = (state_row or {}).get("last_success_at") or None
    if receipt and derived_at:
        return (receipt, "RUN_RECEIPT") if _parse(receipt) >= _parse(derived_at) else (derived_at, "OUTPUT_DERIVED")
    if receipt:
        return receipt, "RUN_RECEIPT"
    if derived_at:
        return derived_at, "OUTPUT_DERIVED"
    return None, "NOT_RECORDED"


def source_monitor_row(
    *,
    producer: str,
    source_ref: str,
    name: str,
    declared_status: str,
    cadence: str,
    last_success_at: Optional[str],
    last_success_basis: str,
    lineage: Dict[str, Any],
    created_at: str,
    extracted_at: str,
    synthetic: bool = False,
    producer_family: Optional[str] = None,
    evidence_tier: Optional[str] = None,
    cadence_window_seconds: Optional[int] = None,
    last_attempt_at: Optional[str] = None,
    last_attempt_status: Optional[str] = None,
    source_url: Optional[str] = None,
    registry_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Build one schema-valid ``source_monitors`` row, failing loudly on bad input."""
    if not producer or not source_ref or not name:
        raise ValueError("producer, source_ref and name are required")
    if declared_status not in DECLARED_STATUSES:
        raise ValueError(f"declared_status {declared_status!r} not in {DECLARED_STATUSES}")
    if cadence not in CADENCES:
        raise ValueError(f"cadence {cadence!r} not in {CADENCES}")
    if last_success_basis not in BASES:
        raise ValueError(f"last_success_basis {last_success_basis!r} not in {BASES}")
    if (last_success_basis == "NOT_RECORDED") != (last_success_at is None):
        raise ValueError("last_success_at must be null exactly when the basis is NOT_RECORDED")
    if evidence_tier is not None and evidence_tier not in TIERS:
        raise ValueError(f"evidence_tier {evidence_tier!r} not in {TIERS}")
    if last_attempt_status is not None and last_attempt_status not in ATTEMPT_STATUSES:
        raise ValueError(f"last_attempt_status {last_attempt_status!r} not in {ATTEMPT_STATUSES}")
    if cadence_window_seconds is not None and int(cadence_window_seconds) < 1:
        raise ValueError("cadence_window_seconds must be positive")
    return {
        "monitor_id": monitor_id(producer, source_ref),
        "source_ref": source_ref,
        "name": name,
        "producer_family": producer_family,
        "evidence_tier": evidence_tier,
        "declared_status": declared_status,
        "cadence": cadence,
        "cadence_window_seconds": int(cadence_window_seconds) if cadence_window_seconds is not None else None,
        "last_success_basis": last_success_basis,
        "last_success_at": last_success_at,
        "last_attempt_at": last_attempt_at,
        "last_attempt_status": last_attempt_status,
        "source_url": source_url,
        "registry_path": registry_path,
        "lineage": lineage,
        "synthetic": bool(synthetic),
        "created_at": created_at,
        "extracted_at": extracted_at,
    }


class SourceRunState:
    """The committed per-producer record of fetch runs, one row per source.

    File shape::

        {"schema_version": "prii_source_run_state_v1",
         "sources": {"<source_id>": {"last_attempt_at": ..., "last_attempt_status": ...,
                                      "last_success_at": ...}}}

    Each run overwrites its source's row; the file is written atomically with
    sorted keys so a run produces a small, stable diff.
    """

    def __init__(self, path: Path, sources: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        self.path = Path(path)
        self.sources: Dict[str, Dict[str, Any]] = dict(sources or {})

    @classmethod
    def load(cls, path: Path) -> "SourceRunState":
        p = Path(path)
        if not p.exists():
            return cls(p)
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("schema_version") != STATE_SCHEMA_VERSION:
            raise ValueError(f"{p}: unexpected schema_version {data.get('schema_version')!r}")
        sources = data.get("sources")
        if not isinstance(sources, dict):
            raise ValueError(f"{p}: 'sources' must be a mapping")
        return cls(p, sources)

    def get(self, source_id: str) -> Optional[Dict[str, Any]]:
        return self.sources.get(source_id)

    def record(self, source_id: str, status: str, at: Optional[str] = None) -> Dict[str, Any]:
        if status not in ATTEMPT_STATUSES:
            raise ValueError(f"status {status!r} not in {ATTEMPT_STATUSES}")
        when = at or utc_now()
        _parse(when)
        row = dict(self.sources.get(source_id) or {})
        row["last_attempt_at"] = when
        row["last_attempt_status"] = status
        if status == "success":
            row["last_success_at"] = when
        row.setdefault("last_success_at", None)
        self.sources[source_id] = row
        return row

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps(
            {"schema_version": STATE_SCHEMA_VERSION, "sources": self.sources},
            indent=2, sort_keys=True,
        ) + "\n"
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".source_run_state.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(body)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        return self.path


def record_run(path: Path, source_id: str, status: str, at: Optional[str] = None) -> Dict[str, Any]:
    """Load the state file, record one run for ``source_id`` and save it."""
    state = SourceRunState.load(path)
    row = state.record(source_id, status, at)
    state.save()
    return row
