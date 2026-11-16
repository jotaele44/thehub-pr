"""Hub-side source monitor: normalize producer source registries (ADR 0012).

Each producer keeps its own registry of the sources it monitors, in its own
shape. Only moneysweep-pr's (a CSV) is still read here; the other five
producers report through the ``source_monitors`` stream. None of those
registries crosses the federation contract: the frozen
``federation_export_manifest`` carried seven canonical streams and no
monitoring fields until ADR 0013 added the optional ``source_monitors``
stream. ADR 0012 records this module as a scoped, temporary exception to
the artifact-only boundary of ADR 0001:

* **Read-only.** It reads registry files from producer checkouts in a
  workspace (the same ``--root`` layout ``hub maintenance`` and
  ``hub validate-federation`` read) and never writes to a producer.
* **Fail-soft.** A missing checkout, file or column is recorded in the summary
  under that producer's ``errors``; it never raises, so one drifted registry
  cannot hide the others.
* **Hub-derived, not a stream.** The output (``monitored_sources.jsonl`` plus
  ``monitored_sources_summary.json``) lands beside the aggregate and is loaded
  by ``hub ingest`` into the ``MonitoredSources`` collection. It is not added
  to ``STREAM_TO_COLLECTION``.
* **Superseded per producer (ADR 0013).** A producer that emits the
  ``source_monitors`` federation stream is read from the stream instead: ingest
  drops this module's rows for that producer. Once a producer emits the
  stream it moves from ``REGISTRIES`` to ``STREAM_PRODUCERS``. moneysweep-pr
  is the last producer in ``REGISTRIES``; when it emits, ADR 0013 deletes this
  module and its CLI.

Freshness for the producer read here is **producer-level**: the
``created_at`` of the producer's export-package manifest, the same field
``hub.federation_status`` reads, because no registry records a per-source
last-successful-poll time. Producers in ``STREAM_PRODUCERS`` report a
per-source ``last_success_at`` with its basis in the stream instead (ADR 0013;
``NOT_RECORDED`` where they keep none). This module reads none of their
registries; it still reads their export-package manifest, so the summary keeps
their ``package_created_at``.

Producer families are kept verbatim (``producer_family``). There is no shared
category taxonomy across producers yet, so none is invented here.
"""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .federation_status import _producer_base
from .ingest import MONITOR_SUMMARY_FILE, MONITORED_SOURCES_FILE
from .registry import Producer, Registry

SUMMARY_SCHEMA_VERSION = "prii_source_monitor_v1"
ADAPTER_VERSION = "source_monitor_v1"

CADENCES = (
    "realtime", "hourly", "daily", "weekly", "monthly", "quarterly", "yearly",
    "event", "static", "manual", "unknown",
)
STATUSES = ("active", "partial", "not_active", "manual", "inactive", "unknown")

# Nominal window per named cadence. event/static/manual/unknown have no window:
# nothing says when the next update is due, so no staleness can be computed.
CADENCE_WINDOW_SECONDS: Dict[str, int] = {
    "realtime": 3600,
    "hourly": 3600,
    "daily": 86400,
    "weekly": 7 * 86400,
    "monthly": 31 * 86400,
    "quarterly": 92 * 86400,
    "yearly": 366 * 86400,
}

# Producer cadence vocabularies -> CADENCES, for the producers in REGISTRIES.
# Keys are lower-cased raw values pinned from their registries as of 2026-11
# (see tests/test_source_monitor.py). Anything not listed normalizes to
# "unknown"; the raw value is always kept.
_NAMED_CADENCE: Dict[str, str] = {
    # canonical names, plus moneysweep-pr update_cadence
    "weekly": "weekly", "monthly": "monthly", "quarterly": "quarterly",
    "yearly": "yearly", "daily": "daily", "hourly": "hourly", "manual": "manual",
    "ad_hoc": "event", "on_drop": "event", "one_time": "static",
}

# Declared-status vocabulary (moneysweep-pr pipeline_status) -> STATUSES. This is
# what the producer says about the source, not a health check.
_NAMED_STATUS: Dict[str, str] = {
    "fully_materialized": "active",
    "partially_materialized": "partial",
    "not_materialized": "not_active",
}

_TIER = re.compile(r"^T[1-4]$")


class RegistryShapeError(ValueError):
    """A registry file is present but not in the shape its adapter expects."""


# ── normalizers ───────────────────────────────────────────────────────────────


def normalize_cadence(raw: Any) -> str:
    if raw is None:
        return "unknown"
    key = str(raw).strip().lower()
    return _NAMED_CADENCE.get(key, "unknown")


def normalize_status(raw: Any) -> str:
    if raw is None:
        return "unknown"
    return _NAMED_STATUS.get(str(raw).strip().lower(), "unknown")


def normalize_tier(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    value = str(raw).strip().upper()
    return value if _TIER.match(value) else None


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


# ── registry readers ──────────────────────────────────────────────────────────


def _read_csv(path: Path, required: Sequence[str]) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in required if c not in (reader.fieldnames or [])]
        if missing:
            raise RegistryShapeError(f"missing column(s): {', '.join(missing)}")
        return list(reader)


def _entry(source_id: Any, *, name: Any, family: Any, tier: Any = None,
           cadence_raw: Any = None, cadence: str = "unknown",
           window_seconds: Optional[int] = None, status_raw: Any = None,
           status: str = "unknown",
           raw: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "source_id": _text(source_id),
        "name": _text(name) or _text(source_id),
        "producer_family": _text(family),
        "evidence_tier": normalize_tier(tier),
        "cadence_raw": _text(cadence_raw),
        "cadence": cadence,
        "cadence_window_seconds": window_seconds,
        "status_raw": _text(status_raw),
        "status": status,
        # No registry read here records a source URL; the key stays because
        # MonitoredSources rows from the stream carry one.
        "url": None,
        "raw": _jsonable(raw or {}),
    }


def _parse_moneysweep(path: Path) -> Iterable[Dict[str, Any]]:
    for r in _read_csv(path, ("source_id", "family", "update_cadence", "pipeline_status")):
        cadence = normalize_cadence(r["update_cadence"])
        yield _entry(
            r["source_id"], name=r["source_id"], family=r["family"],
            cadence_raw=r["update_cadence"], cadence=cadence,
            window_seconds=CADENCE_WINDOW_SECONDS.get(cadence),
            status_raw=r["pipeline_status"], status=normalize_status(r["pipeline_status"]), raw=r,
        )


Parser = Callable[[Path], Iterable[Dict[str, Any]]]

# producer program_id -> [(registry path relative to the checkout, parser)].
# One-spot edit when a producer moves or reshapes its registry.
REGISTRIES: Dict[str, List[Tuple[str, Parser]]] = {
    "moneysweep-pr": [("reports/source_registry_status.csv", _parse_moneysweep)],
}

# Producers that report their sources in the source_monitors stream (ADR 0013).
# Their registries are no longer read here; ingest takes their rows from the
# stream and flags them when an aggregate has none.
STREAM_PRODUCERS: frozenset = frozenset(
    {"aguayluz-pr", "ovnis-pr", "spiderweb-pr", "skywatcher-pr", "centinelas-pr"}
)


# ── build ─────────────────────────────────────────────────────────────────────


def _package_created_at(base: Path, producer: Producer) -> Optional[str]:
    """Producer-level freshness: the export package manifest's ``created_at``."""
    try:
        manifest = json.loads((base / producer.export_path / "manifest.json").read_text())
    except (OSError, ValueError):
        return None
    value = manifest.get("created_at") if isinstance(manifest, dict) else None
    return str(value) if value else None


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_monitor(registry: Registry, root: str | Path,
                  now: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Normalize every registered producer's source registries.

    Returns ``(rows, summary)``. Rows are sorted by ``monitor_id``. Problems are
    recorded per producer in ``summary["producers"][id]["errors"]``; nothing raises.
    """
    root_path = Path(root)
    generated_at = now or _now_iso()
    rows: List[Dict[str, Any]] = []
    producers: Dict[str, Dict[str, Any]] = {}

    for producer in registry.producers:
        pid = producer.program_id
        base = _producer_base(root_path, producer)
        package_at = _package_created_at(base, producer)
        info: Dict[str, Any] = {
            "checkout_present": base.exists(),
            "package_created_at": package_at,
            "registries": [],
            "count": 0,
            # No registry read here excludes sources today; the key stays because
            # the summary shape (and the Source Monitor page) carries it.
            "excluded": {},
            "errors": [],
        }
        producers[pid] = info
        if pid in STREAM_PRODUCERS:
            info["reports_via_stream"] = True
            continue
        adapters = REGISTRIES.get(pid)
        if not adapters:
            info["errors"].append("no registry adapter for this producer")
            continue
        if not info["checkout_present"]:
            info["errors"].append(f"checkout not found at {base}")
            continue
        seen: set = set()
        for rel, parser in adapters:
            info["registries"].append(rel)
            path = base / rel
            if not path.exists():
                info["errors"].append(f"{rel}: file not found")
                continue
            try:
                entries = list(parser(path))
            except (RegistryShapeError, OSError, ValueError, KeyError) as exc:
                info["errors"].append(f"{rel}: {exc}")
                continue
            for e in entries:
                sid = e.get("source_id")
                if not sid:
                    info["errors"].append(f"{rel}: row without a source id skipped")
                    continue
                if sid in seen:
                    info["errors"].append(f"{rel}: duplicate source id {sid!r} skipped")
                    continue
                seen.add(sid)
                rows.append({
                    **e,
                    "monitor_id": f"{pid}:{sid}",
                    "producer": pid,
                    "producer_last_package_at": package_at,
                    "lineage": {"registry_path": rel, "adapter": ADAPTER_VERSION},
                    "observed_at": generated_at,
                })
                info["count"] += 1

    rows.sort(key=lambda r: r["monitor_id"])
    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "adapter": ADAPTER_VERSION,
        "generated_at": generated_at,
        "root": str(root_path),
        "total": len(rows),
        "error_count": sum(len(p["errors"]) for p in producers.values()),
        "producers": producers,
    }
    return rows, summary


def write_monitor(rows: List[Dict[str, Any]], summary: Dict[str, Any],
                  out_dir: str | Path) -> Tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows_path = out / MONITORED_SOURCES_FILE
    summary_path = out / MONITOR_SUMMARY_FILE
    rows_path.write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8"
    )
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return rows_path, summary_path
