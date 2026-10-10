"""Additive Cell_Profile V2 contract for PR_GRID_GEOGRAPHIC_V2.

V1 cell_profile@1 remains frozen and unchanged. This module binds V2 profiles to
the fail-closed grid runtime and never carries canonical geometry.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from hub.grid_v2 import (
    GRID_ID,
    GRID_VERSION,
    GridV2Pin,
    GridV2PinError,
    build_grid_deep_link,
    grid_identity,
    validate_cell_id,
    validate_level,
)

CONTRACT_VERSION = "pr-grid-v2-cell-profile/1.0"
IDENTITY_DEFAULT = "CANDIDATE_NOT_IDENTITY"
DATA_STATES = frozenset(
    {"HAS_DATA", "ZERO_RECORDS", "NO_DATA", "NOT_APPLICABLE", "UNKNOWN", "STALE"}
)
MIGRATION_STATES = frozenset(
    {
        "RECOMPUTED_FROM_SOURCE_GEOMETRY",
        "RECOMPUTED_FROM_SOURCE_COORDINATE",
        "VERIFIED_CROSSWALK",
        "PROVISIONAL_CROSSWALK",
        "AMBIGUOUS",
        "UNMIGRATED",
    }
)
REPOSITORIES = frozenset(
    {
        "spiderweb-pr",
        "aguayluz-pr",
        "skywatcher-pr",
        "centinelas-pr",
        "moneysweep-pr",
        "ovnis-pr",
        "thehub-pr",
    }
)
_FORBIDDEN_GEOMETRY_FIELDS = frozenset({"geometry", "coordinates", "bbox", "polygon"})


class CellProfileV2Error(ValueError):
    """Raised when a V2 cell profile violates identity or data-state semantics."""


def _validate_data_state(
    *,
    data_state: str,
    record_count: int | None,
    migration_state: str,
) -> None:
    if data_state not in DATA_STATES:
        raise CellProfileV2Error(f"unknown Data_State: {data_state!r}")
    if migration_state not in MIGRATION_STATES:
        raise CellProfileV2Error(f"unknown Migration_State: {migration_state!r}")
    if isinstance(record_count, bool):
        raise CellProfileV2Error("Record_Count must be an integer or null")

    if data_state == "HAS_DATA":
        if not isinstance(record_count, int) or record_count < 1:
            raise CellProfileV2Error("HAS_DATA requires Record_Count >= 1")
    elif data_state == "ZERO_RECORDS":
        if record_count != 0:
            raise CellProfileV2Error("ZERO_RECORDS requires Record_Count == 0")
    elif record_count is not None:
        raise CellProfileV2Error(f"{data_state} requires Record_Count = null")

    if migration_state == "UNMIGRATED":
        if data_state not in {"UNKNOWN", "NOT_APPLICABLE"}:
            raise CellProfileV2Error("UNMIGRATED cannot claim observed cell data")
        if record_count is not None:
            raise CellProfileV2Error("UNMIGRATED requires Record_Count = null")


def build_cell_profile_v2(
    pin: GridV2Pin,
    *,
    repository: str,
    profile_type: str,
    level: str,
    cell_id: str,
    data_state: str,
    record_count: int | None,
    migration_state: str,
    summary: Mapping[str, Any] | None = None,
    categories: list[Mapping[str, Any]] | None = None,
    top_record_ids: list[str] | None = None,
    completeness: Mapping[str, Any] | None = None,
    updated_at: str | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Build one canonical V2 profile or fail closed."""
    if repository not in REPOSITORIES:
        raise CellProfileV2Error(f"unknown Repository: {repository!r}")
    if not isinstance(profile_type, str) or not profile_type.strip():
        raise CellProfileV2Error("Profile_Type is required")

    selected_level = validate_level(level)
    try:
        canonical_cell = validate_cell_id(cell_id, level=selected_level)
    except GridV2PinError as exc:
        raise CellProfileV2Error(str(exc)) from exc

    _validate_data_state(
        data_state=data_state,
        record_count=record_count,
        migration_state=migration_state,
    )

    records = list(top_record_ids or [])
    if len(records) > 25:
        raise CellProfileV2Error("Top_Record_IDs exceeds the 25-identifier ceiling")
    if any(not isinstance(value, str) or not value for value in records):
        raise CellProfileV2Error("Top_Record_IDs must contain non-empty identifiers only")

    summary_payload = dict(summary or {})
    forbidden = sorted(_FORBIDDEN_GEOMETRY_FIELDS.intersection(summary_payload))
    if forbidden:
        raise CellProfileV2Error(
            "cell profile Summary must not carry canonical geometry: " + ", ".join(forbidden)
        )

    identity = grid_identity(pin, level=selected_level, cell_id=canonical_cell)
    if identity["Grid_ID"] != GRID_ID or identity["Grid_Version"] != GRID_VERSION:
        raise CellProfileV2Error("runtime grid identity mismatch")

    return {
        "Contract_Version": CONTRACT_VERSION,
        "Grid_Identity": identity,
        "Repository": repository,
        "Profile_Type": profile_type,
        "Data_State": data_state,
        "Record_Count": record_count,
        "Migration_State": migration_state,
        "Summary": summary_payload,
        "Categories": [dict(value) for value in (categories or [])],
        "Top_Record_IDs": records,
        "Completeness": dict(completeness or {}),
        "Updated_At": updated_at,
        "Geometry_Included": False,
        "Deep_Link": build_grid_deep_link(
            pin,
            level=selected_level,
            cell_id=canonical_cell,
            as_of=as_of,
        ),
        "Identity_Default": IDENTITY_DEFAULT,
    }


def build_unmigrated_hub_profile(
    pin: GridV2Pin,
    *,
    level: str,
    cell_id: str,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Truthful pre-migration Hub response: unknown is not zero."""
    return build_cell_profile_v2(
        pin,
        repository="thehub-pr",
        profile_type="federation_summary",
        level=level,
        cell_id=cell_id,
        data_state="UNKNOWN",
        record_count=None,
        migration_state="UNMIGRATED",
        summary={
            "state_reason": "V2_RECORD_BINDINGS_NOT_MATERIALIZED",
            "zero_records_claimed": False,
            "geometry_available_from": "spiderweb-pr",
        },
        completeness={
            "binding_coverage": "UNMIGRATED",
            "source_coverage": "UNKNOWN",
        },
        as_of=as_of,
    )
