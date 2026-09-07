"""Read-only drought situation projection for the federation Hub.

The Hub joins producer references and display-safe summaries. It never becomes a
third ingest path and never stores canonical hydrologic observations independently.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Mapping, Sequence


_AGUAYLUZ_RECORD_ID = re.compile(r"^AYL_DROUGHT_[A-Z_]+_[0-9a-f]{20}$")
_CENTINELAS_EVENT_ID = re.compile(r"^CEN_DROUGHT_[0-9a-f]{20}$")
_CONTENT_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DROUGHT_KINDS = {
    "classification_observation",
    "hydrologic_indicator",
    "impact_event",
    "water_restriction",
    "outlook",
    "source_document",
}
_IMPACT_TYPES = {
    "wildfire_activity",
    "agricultural_water_shortage",
    "crop_stress",
    "infrastructure_fire_damage",
    "stream_dry_report",
    "water_hauling",
    "forage_shortage",
    "municipal_rationing",
}
_EVIDENCE_TIERS = {"T1", "T2", "T3", "T4"}


def _sha(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _require_member(value: Any, allowed: set[str], field: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"{field} must match the producer contract")
    return value


def _require_pattern(value: Any, pattern: re.Pattern[str], field: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ValueError(f"{field} must match the producer contract")
    return value


def _optional_string(value: Any, field: str) -> str | None:
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{field} must match the producer contract")
    return value


def _require_aware_datetime(value: str, field: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO 8601 date-time") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a UTC offset")


def build_situation_projection(
    *,
    area_id: str,
    valid_at: str,
    aguayluz_records: Sequence[Mapping[str, Any]],
    centinelas_events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Join producer-owned records into one immutable, read-only projection."""

    if not isinstance(area_id, str) or not area_id or area_id != area_id.strip():
        raise ValueError("area_id must be a non-empty string without outer whitespace")
    if not isinstance(valid_at, str):
        raise ValueError("valid_at must be an ISO 8601 date-time")
    _require_aware_datetime(valid_at, "valid_at")

    water_refs: list[dict[str, Any]] = []
    water_ids: set[str] = set()
    for record in aguayluz_records:
        if not isinstance(record, Mapping):
            raise ValueError("AguaYLuz record must match the producer contract")
        record_id = _require_pattern(
            record.get("record_id"), _AGUAYLUZ_RECORD_ID, "AguaYLuz record_id"
        )
        if record_id in water_ids:
            raise ValueError(f"duplicate AguaYLuz record_id: {record_id}")
        water_ids.add(record_id)
        quality = record.get("quality")
        if not isinstance(quality, Mapping):
            raise ValueError("AguaYLuz quality must match the producer contract")
        water_refs.append(
            {
                "record_id": record_id,
                "kind": _require_member(
                    record.get("kind"), _DROUGHT_KINDS, "AguaYLuz kind"
                ),
                "content_sha256": _require_pattern(
                    record.get("content_sha256"),
                    _CONTENT_SHA256,
                    "AguaYLuz content_sha256",
                ),
                "freshness": _optional_string(
                    quality.get("freshness"), "AguaYLuz freshness"
                ),
                "evidence_tier": _require_member(
                    record.get("evidence_tier"),
                    _EVIDENCE_TIERS,
                    "AguaYLuz evidence_tier",
                ),
            }
        )

    impact_refs: list[dict[str, Any]] = []
    impact_ids: set[str] = set()
    for event in centinelas_events:
        if not isinstance(event, Mapping):
            raise ValueError("Centinelas event must match the producer contract")
        event_id = _require_pattern(
            event.get("event_id"), _CENTINELAS_EVENT_ID, "Centinelas event_id"
        )
        if event_id in impact_ids:
            raise ValueError(f"duplicate Centinelas event_id: {event_id}")
        impact_ids.add(event_id)
        if event.get("canonical_hydrology_embedded") is not False:
            raise ValueError("Hub rejects impact events that embed canonical hydrology")
        impact_refs.append(
            {
                "event_id": event_id,
                "impact_type": _require_member(
                    event.get("impact_type"), _IMPACT_TYPES, "Centinelas impact_type"
                ),
                "content_sha256": _require_pattern(
                    event.get("content_sha256"),
                    _CONTENT_SHA256,
                    "Centinelas content_sha256",
                ),
                "evidence_tier": _require_member(
                    event.get("evidence_tier"),
                    _EVIDENCE_TIERS,
                    "Centinelas evidence_tier",
                ),
            }
        )

    identity = {"area_id": area_id, "valid_at": valid_at}
    projection = {
        "schema_version": "thehub.drought-situation/v0.1",
        "projection_id": f"HUB_DROUGHT_{_sha(identity)[:20]}",
        "area_id": area_id,
        "valid_at": valid_at,
        "aguayluz_record_refs": sorted(water_refs, key=lambda item: item["record_id"]),
        "centinelas_event_refs": sorted(impact_refs, key=lambda item: item["event_id"]),
        "read_only": True,
        "independent_ingest": False,
        "canonical_hydrology_embedded": False,
    }
    projection["content_sha256"] = _sha(projection)
    return projection


def assert_zero_duplicate_ingest(projection: Mapping[str, Any]) -> None:
    """Enforce Hub ownership boundaries on a serialized projection."""

    if projection.get("independent_ingest") is not False:
        raise ValueError("TheHub must not independently ingest drought sources")
    if projection.get("canonical_hydrology_embedded") is not False:
        raise ValueError("TheHub must reference, not duplicate, canonical hydrology")
    forbidden = {
        "streamflow_value",
        "groundwater_level",
        "reservoir_level",
        "soil_moisture_value",
        "usdm_geometry",
        "forecast_probability",
    }
    overlap = forbidden.intersection(projection)
    if overlap:
        raise ValueError(f"duplicate canonical fields: {sorted(overlap)}")
