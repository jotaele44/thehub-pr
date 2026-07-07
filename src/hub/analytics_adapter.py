"""Adapt a Hub aggregate into Federation Analytics v2 input records.

``federation_analytics_v2`` was written against a hand-staged
``data/federation_analytics_v2/records.jsonl`` using non-canonical fields
(``corridor_id``, ``domain``, ``event_count``, ``anomaly_score``, ``producer``)
that no producer emits. This adapter closes that gap: it reads the *canonical*
aggregate (``observations`` + ``alerts`` — the event-bearing, time-stamped,
located streams) and maps existing canonical fields onto the shape the analytics
layer expects, so the seasonality/threshold/cross-repo analysis runs on real
federation data instead of a disconnected fixture.

Mapping (canonical row -> analytics record):

* ``observed_at``  <- row ``observed_at``           (both streams carry it)
* ``corridor_id``  <- ``location.municipality``      (upper-cased; else ``unassigned``)
* ``domain``       <- stream label (``observation`` / ``alert``)
* ``event_count``  <- 1                              (one row == one event)
* ``anomaly_score``<- row ``confidence``
* ``producer``     <- first of the aggregate's ``_producers`` provenance list

Entities are intentionally excluded: they carry only extraction provenance
(``extracted_at``), not an event timestamp, so folding them in would fabricate a
seasonality signal. Rows without an ``observed_at`` are dropped (honest: no event
time, no seasonality/window membership).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

# Canonical event-bearing streams and the domain label each maps to.
_EVENT_STREAMS = {"observations": "observation", "alerts": "alert"}


def _read_stream(agg_dir: Path, stream: str) -> List[Dict[str, Any]]:
    fpath = agg_dir / f"{stream}.jsonl"
    if not fpath.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for raw in fpath.read_text().splitlines():
        raw = raw.strip()
        if raw:
            rows.append(json.loads(raw))
    return rows


def _corridor(row: Dict[str, Any]) -> str:
    loc = row.get("location")
    if isinstance(loc, dict):
        muni = loc.get("municipality")
        if isinstance(muni, str) and muni.strip():
            return muni.strip().upper()
    return "unassigned"


def _producers(row: Dict[str, Any]) -> List[str]:
    """Every producer that contributed the row (aggregate stamps ``_producers``).

    One record is emitted per producer so a row corroborated by two producers in
    the same corridor/time window yields a cross-repo correlation instead of
    collapsing to a single repo. ``correlate_cross_repo_anomalies`` needs >= 2
    distinct producers in a bucket to emit an edge, so preserving the full set is
    what makes multi-producer corroboration visible. Seasonality groups by
    corridor/domain/time (not producer), so the per-producer fan-out does not
    distort it."""
    producers = row.get("_producers")
    if isinstance(producers, list) and producers:
        return sorted(str(p) for p in producers)
    return ["unknown"]


def aggregate_to_analytics_records(aggregate_dir: str | Path) -> List[Dict[str, Any]]:
    """Build Federation Analytics v2 input records from a Hub aggregate directory.

    Deterministic: streams are read in a fixed order, rows in file order, and
    producers sorted, so the same aggregate yields byte-identical records."""
    agg = Path(aggregate_dir)
    records: List[Dict[str, Any]] = []
    for stream, domain in _EVENT_STREAMS.items():
        for row in _read_stream(agg, stream):
            observed_at = row.get("observed_at")
            if not observed_at:
                continue
            conf = row.get("confidence")
            score = float(conf) if isinstance(conf, (int, float)) else 0.5
            corridor = _corridor(row)
            for producer in _producers(row):
                records.append({
                    "observed_at": observed_at,
                    "corridor_id": corridor,
                    "domain": domain,
                    "event_count": 1,
                    "producer": producer,
                    "anomaly_score": score,
                })
    return records
