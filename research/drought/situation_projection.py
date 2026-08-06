"""Read-only drought situation projection for the federation Hub.

The Hub joins producer references and display-safe summaries. It never becomes a
third ingest path and never stores canonical hydrologic observations independently.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence


def _sha(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_situation_projection(
    *,
    area_id: str,
    valid_at: str,
    aguayluz_records: Sequence[Mapping[str, Any]],
    centinelas_events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Join producer-owned records into one immutable, read-only projection."""

    if not area_id.strip():
        raise ValueError("area_id is required")

    water_refs: list[dict[str, Any]] = []
    for record in aguayluz_records:
        record_id = str(record.get("record_id", ""))
        if not record_id.startswith("AYL_DROUGHT_"):
            raise ValueError("AguaYLuz drought records require canonical record IDs")
        water_refs.append(
            {
                "record_id": record_id,
                "kind": record.get("kind"),
                "content_sha256": record.get("content_sha256"),
                "freshness": record.get("quality", {}).get("freshness"),
                "evidence_tier": record.get("evidence_tier"),
            }
        )

    impact_refs: list[dict[str, Any]] = []
    for event in centinelas_events:
        event_id = str(event.get("event_id", ""))
        if not event_id.startswith("CEN_DROUGHT_"):
            raise ValueError("Centinelas drought events require canonical event IDs")
        if event.get("canonical_hydrology_embedded") is not False:
            raise ValueError("Hub rejects impact events that embed canonical hydrology")
        impact_refs.append(
            {
                "event_id": event_id,
                "impact_type": event.get("impact_type"),
                "content_sha256": event.get("content_sha256"),
                "evidence_tier": event.get("evidence_tier"),
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
