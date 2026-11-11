"""Hub-side source monitor: normalize producer source registries (ADR 0012).

Each producer keeps its own registry of the sources it monitors, in its own
shape (a CSV in moneysweep-pr, YAML in skywatcher-pr, JSON families in
aguayluz-pr, ...). None of that crosses the federation contract: the frozen
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
  drops this module's rows for that producer. Remove a producer from
  ``REGISTRIES`` once it emits the stream; delete this module when all six do.

Freshness here is **producer-level**: the ``created_at`` of the producer's
export-package manifest, the same field ``hub.federation_status`` reads. No
registry records a per-source last-successful-poll time; that needs the
deferred ``source_monitors`` stream (ADR 0012, phase 2).

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

import yaml

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

# Producer cadence vocabularies -> CADENCES. Keys are lower-cased raw values
# pinned from the registries as of 2026-11 (see tests/test_source_monitor.py).
# Anything not listed normalizes to "unknown"; the raw value is always kept.
_NAMED_CADENCE: Dict[str, str] = {
    # moneysweep-pr update_cadence / ovnis-pr retrieval_cadence
    "weekly": "weekly", "monthly": "monthly", "quarterly": "quarterly",
    "yearly": "yearly", "annual": "yearly", "daily": "daily", "hourly": "hourly",
    "ad_hoc": "event", "on_drop": "event", "on_foia_release": "event",
    "on_legacy_consolidation": "event", "one_time": "static", "none": "static",
    "manual": "manual",
    # spiderweb-pr refresh_policy
    "pin_by_vintage": "static",
    "probe_service_then_snapshot_if_changed": "event",
    "probe_sciencebase_item_then_snapshot_if_changed": "event",
    # skywatcher-pr mode
    "delayed_or_rate_limited": "realtime", "batch_file": "event",
    "historical_baseline": "static",
}

# Declared-status vocabularies -> STATUSES. This is what the producer says about
# the source, not a health check.
_NAMED_STATUS: Dict[str, str] = {
    # moneysweep-pr pipeline_status
    "fully_materialized": "active",
    "partially_materialized": "partial",
    "not_materialized": "not_active",
    # centinelas-pr / ovnis-pr active
    "active": "active", "manual": "manual", "yes": "active", "no": "inactive",
    # spiderweb-pr missing-persons status
    "harvester_landed": "active", "harvester_planned": "not_active",
    "manual_pull": "manual", "aggregate_only": "partial", "cannot_reach": "inactive",
}

_TIER = re.compile(r"^T[1-4]$")

# Largest-first buckets for cadences declared in seconds/days; a 25% tolerance
# keeps e.g. 90 days in "quarterly" and 86400 s in "daily".
_SECOND_BUCKETS: Tuple[Tuple[str, int], ...] = (
    ("yearly", CADENCE_WINDOW_SECONDS["yearly"]),
    ("quarterly", CADENCE_WINDOW_SECONDS["quarterly"]),
    ("monthly", CADENCE_WINDOW_SECONDS["monthly"]),
    ("weekly", CADENCE_WINDOW_SECONDS["weekly"]),
    ("daily", CADENCE_WINDOW_SECONDS["daily"]),
    ("hourly", CADENCE_WINDOW_SECONDS["hourly"]),
)


class RegistryShapeError(ValueError):
    """A registry file is present but not in the shape its adapter expects."""


# ── normalizers ───────────────────────────────────────────────────────────────


def normalize_cadence(raw: Any) -> str:
    if raw is None:
        return "unknown"
    key = str(raw).strip().lower()
    return _NAMED_CADENCE.get(key, "unknown")


def cadence_from_seconds(seconds: Any) -> str:
    try:
        s = float(seconds)
    except (TypeError, ValueError):
        return "unknown"
    if s <= 0:
        return "unknown"
    for name, nominal in _SECOND_BUCKETS:
        if s * 1.25 >= nominal:
            return name
    return "realtime"


def cadence_from_text(text: Any) -> str:
    """First word of a free-text cadence ("weekly; records may be revised")."""
    if not isinstance(text, str) or not text.strip():
        return "unknown"
    first = re.split(r"[\s;,.]+", text.strip().lower(), maxsplit=1)[0]
    return _NAMED_CADENCE.get(first, "unknown")


def normalize_status(raw: Any) -> str:
    if raw is None:
        return "unknown"
    return _NAMED_STATUS.get(str(raw).strip().lower(), "unknown")


def binding_status(raw: Any) -> str:
    """aguayluz-pr hazard-family binding state (BOUND…/CERTIFIED…/OPEN…)."""
    if not isinstance(raw, str) or not raw.strip():
        return "unknown"
    s = raw.strip().upper()
    if s.startswith("OPEN"):
        return "not_active"
    if "OPEN" in s or "UNRESOLVED" in s:
        return "partial"
    if s.startswith(("BOUND", "CERTIFIED")):
        return "active"
    return "unknown"


def normalize_tier(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    value = str(raw).strip().upper()
    return value if _TIER.match(value) else None


def _window(cadence: str, declared_seconds: Any = None) -> Optional[int]:
    """A producer-declared window in seconds wins; otherwise the cadence's nominal one."""
    try:
        declared = float(declared_seconds) if declared_seconds is not None else 0.0
    except (TypeError, ValueError):
        # A non-numeric declared window is ignored rather than trusted.
        declared = 0.0
    if declared > 0:
        return int(declared)
    return CADENCE_WINDOW_SECONDS.get(cadence)


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


def _read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _require(container: Any, key: str, kind: type) -> Any:
    value = container.get(key) if isinstance(container, dict) else None
    if not isinstance(value, kind):
        raise RegistryShapeError(f"expected top-level {key!r} {kind.__name__}")
    return value


def _entry(source_id: Any, *, name: Any, family: Any, tier: Any = None,
           cadence_raw: Any = None, cadence: str = "unknown",
           window_seconds: Optional[int] = None, status_raw: Any = None,
           status: str = "unknown", url: Any = None,
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
        "url": _text(url),
        "raw": _jsonable(raw or {}),
    }


def _parse_moneysweep(path: Path) -> Iterable[Dict[str, Any]]:
    for r in _read_csv(path, ("source_id", "family", "update_cadence", "pipeline_status")):
        cadence = normalize_cadence(r["update_cadence"])
        yield _entry(
            r["source_id"], name=r["source_id"], family=r["family"],
            cadence_raw=r["update_cadence"], cadence=cadence, window_seconds=_window(cadence),
            status_raw=r["pipeline_status"], status=normalize_status(r["pipeline_status"]), raw=r,
        )


def _parse_centinelas(path: Path) -> Iterable[Dict[str, Any]]:
    # reliability_default is a 0..1 score here, not a T-tier: kept in raw only.
    for r in _read_csv(path, ("source_id", "name", "source_family", "active", "scrape_method")):
        cadence = "manual" if r["scrape_method"].strip().lower() == "manual" else "unknown"
        yield _entry(
            r["source_id"], name=r["name"], family=r["source_family"],
            cadence=cadence, status_raw=r["active"], status=normalize_status(r["active"]), raw=r,
        )


def _parse_ovnis(path: Path) -> Iterable[Dict[str, Any]]:
    cols = ("source_id", "name", "source_family", "reliability_default", "active", "retrieval_cadence")
    for r in _read_csv(path, cols):
        cadence = normalize_cadence(r["retrieval_cadence"])
        yield _entry(
            r["source_id"], name=r["name"], family=r["source_family"], tier=r["reliability_default"],
            cadence_raw=r["retrieval_cadence"], cadence=cadence, window_seconds=_window(cadence),
            status_raw=r["active"], status=normalize_status(r["active"]), raw=r,
        )


def _parse_spiderweb_hydrography(path: Path) -> Iterable[Dict[str, Any]]:
    cols = ("source_id", "authority", "universe", "refresh_policy", "evidence_tier")
    for r in _read_csv(path, cols):
        cadence = normalize_cadence(r["refresh_policy"])
        yield _entry(
            r["source_id"], name=f"{r['authority']}: {r['universe']}", family=r["universe"],
            tier=r["evidence_tier"], cadence_raw=r["refresh_policy"], cadence=cadence,
            window_seconds=_window(cadence), url=r.get("endpoint"), raw=r,
        )


def _parse_spiderweb_missing_persons(path: Path) -> Iterable[Dict[str, Any]]:
    sources = _require(_read_yaml(path), "sources", dict)
    for sid, s in sources.items():
        if not isinstance(s, dict):
            raise RegistryShapeError(f"source {sid!r} is not a mapping")
        # The producer marks these never-federated (raw PII, ToS, stratum C);
        # the hub does not surface them, it only counts them.
        if s.get("federation_eligible") is False:
            yield {"_excluded": "not_federation_eligible"}
            continue
        days = s.get("refresh_cadence_days")
        seconds = float(days) * 86400 if isinstance(days, (int, float)) and days > 0 else None
        # 0 days marks a one-off dataset or per-event backfill: nothing recurs.
        cadence = "static" if days == 0 else cadence_from_seconds(seconds)
        yield _entry(
            sid, name=s.get("operator"), family="missing_persons",
            cadence_raw=f"{days} days" if days is not None else None, cadence=cadence,
            window_seconds=_window(cadence, seconds), status_raw=s.get("status"),
            status=normalize_status(s.get("status")), url=s.get("url"), raw=s,
        )


def _parse_skywatcher(path: Path) -> Iterable[Dict[str, Any]]:
    data = _read_yaml(path)
    if not isinstance(data, dict):
        raise RegistryShapeError("expected a mapping of domain -> source list")
    for domain, items in data.items():
        if not isinstance(items, list):
            continue
        for s in items:
            if not isinstance(s, dict) or "id" not in s:
                raise RegistryShapeError(f"{domain}: entry without 'id'")
            cadence = normalize_cadence(s.get("mode"))
            yield _entry(
                s["id"], name=s.get("use"), family=domain, tier=s.get("tier"),
                cadence_raw=s.get("mode"), cadence=cadence, window_seconds=_window(cadence), raw=s,
            )


def _parse_aguayluz_hydromet(path: Path) -> Iterable[Dict[str, Any]]:
    for s in _require(_read_json(path), "sources", list):
        if not isinstance(s, dict) or "source_id" not in s:
            raise RegistryShapeError("source entry without 'source_id'")
        cadence = cadence_from_seconds(s.get("cadence_seconds"))
        declared = s.get("max_age_seconds") or s.get("cadence_seconds")
        yield _entry(
            s["source_id"], name=s.get("label"), family=s.get("family"),
            cadence_raw=f"{s.get('cadence_seconds')} s" if s.get("cadence_seconds") else None,
            cadence=cadence, window_seconds=_window(cadence, declared), raw=s,
        )


def _family_name(f: Dict[str, Any]) -> str:
    return f"{f['authority']}: {f['family']}" if f.get("authority") else f["family"]


def _parse_aguayluz_hazard(path: Path) -> Iterable[Dict[str, Any]]:
    for f in _require(_read_json(path), "families", list):
        if not isinstance(f, dict) or "family" not in f:
            raise RegistryShapeError("family entry without 'family'")
        cadence = cadence_from_text(f.get("update_semantics"))
        yield _entry(
            f["family"], name=_family_name(f), family=f.get("hazard_family"),
            cadence_raw=f.get("update_semantics"), cadence=cadence, window_seconds=_window(cadence),
            status_raw=f.get("status"), status=binding_status(f.get("status")), url=f.get("url"), raw=f,
        )


def _parse_aguayluz_exposure(path: Path) -> Iterable[Dict[str, Any]]:
    for f in _require(_read_json(path), "families", list):
        if not isinstance(f, dict) or "family" not in f:
            raise RegistryShapeError("family entry without 'family'")
        yield _entry(
            f["family"], name=_family_name(f), family="ENVIRONMENTAL_EXPOSURE",
            url=f.get("discovery_locator"), raw=f,
        )


Parser = Callable[[Path], Iterable[Dict[str, Any]]]

# producer program_id -> [(registry path relative to the checkout, parser)].
# One-spot edit when a producer moves or reshapes its registry.
REGISTRIES: Dict[str, List[Tuple[str, Parser]]] = {
    "moneysweep-pr": [("reports/source_registry_status.csv", _parse_moneysweep)],
    "centinelas-pr": [("data/reference/source_registry.csv", _parse_centinelas)],
    "ovnis-pr": [("data/reference/source_registry.csv", _parse_ovnis)],
    "spiderweb-pr": [
        ("manifests/pr_hydrography/source_registry.csv", _parse_spiderweb_hydrography),
        ("configs/missing_persons_sources.yaml", _parse_spiderweb_missing_persons),
    ],
    "skywatcher-pr": [("registry/source_registry.yaml", _parse_skywatcher)],
    "aguayluz-pr": [
        ("config/hydromet_sources.v1.json", _parse_aguayluz_hydromet),
        ("config/hazard_advisory_sources.v1.json", _parse_aguayluz_hazard),
        ("config/environmental_exposure_sources.v1.json", _parse_aguayluz_exposure),
    ],
}


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
            "excluded": {},
            "errors": [],
        }
        producers[pid] = info
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
            except (RegistryShapeError, OSError, ValueError, yaml.YAMLError, KeyError) as exc:
                info["errors"].append(f"{rel}: {exc}")
                continue
            for e in entries:
                if "_excluded" in e:
                    reason = e["_excluded"]
                    info["excluded"][reason] = info["excluded"].get(reason, 0) + 1
                    continue
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
