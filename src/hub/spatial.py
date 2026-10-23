"""Federation spatial-sidecar discovery and cross-producer query primitives.

The Hub is the sole cross-producer correlation authority. Producer geometry is
context/evidence only and MUST NOT establish canonical identity.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

SPATIAL_MANIFEST_VERSION = "federation-spatial-manifest/1.0"
SPATIAL_CONTRACT_VERSION = "federation-spatial-contract/1.0"
IDENTITY_DEFAULT = "CANDIDATE_NOT_IDENTITY"
HUB_AUTHORITY = "thehub-pr"

# Federation spatial index (generation federation-spatial-index/1).
GEOMETRY_AUTHORITY = "spiderweb-pr"
CELL_ID_PATTERN = re.compile(r"^R(?:0|[1-9][0-9]{0,2})_C(?:0|[1-9][0-9]{0,2})$")
CELL_ROW_MAX = 255
CELL_COLUMN_MAX = 383
CERTIFICATION_STATES = frozenset({"VERIFIED", "PROVISIONAL"})
PRODUCER_REPOS = frozenset(
    {
        "spiderweb-pr",
        "aguayluz-pr",
        "skywatcher-pr",
        "centinelas-pr",
        "moneysweep-pr",
        "ovnis-pr",
    }
)


class SpatialContractError(ValueError):
    """Raised when a producer violates the federation spatial contract."""


@dataclass(frozen=True)
class SpatialProducer:
    producer_repo: str
    authority: str
    frozen_base_sha: str
    manifest: Mapping[str, object]


def validate_spatial_manifest(manifest: Mapping[str, object]) -> list[str]:
    errors: list[str] = []
    if manifest.get("contract_version") != SPATIAL_MANIFEST_VERSION:
        errors.append("unsupported spatial manifest version")
    producer = manifest.get("producer_repo")
    if not isinstance(producer, str) or not producer:
        errors.append("producer_repo is required")
    cross_repo = manifest.get("cross_repo")
    if not isinstance(cross_repo, Mapping):
        errors.append("cross_repo object is required")
    else:
        if cross_repo.get("identity_default") != IDENTITY_DEFAULT:
            errors.append("identity_default must be CANDIDATE_NOT_IDENTITY")
        if cross_repo.get("hub_correlation_authority") != HUB_AUTHORITY:
            errors.append("cross-producer correlation authority must remain thehub-pr")
    storage = manifest.get("storage")
    if not isinstance(storage, Mapping) or storage.get("ownership") != "REPO_LOCAL":
        errors.append("producer spatial storage ownership must be REPO_LOCAL")
    contracts = manifest.get("contracts")
    if not isinstance(contracts, Mapping) or not contracts:
        errors.append("contracts object is required")
    return errors


def load_spatial_manifest(path: str | Path) -> SpatialProducer:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    errors = validate_spatial_manifest(data)
    if errors:
        raise SpatialContractError("; ".join(errors))
    return SpatialProducer(
        producer_repo=str(data["producer_repo"]),
        authority=str(data.get("domain_authority", "")),
        frozen_base_sha=str(data.get("frozen_base_sha", "")),
        manifest=data,
    )


def validate_spatial_feature(feature: Mapping[str, object], producer_repo: str) -> list[str]:
    errors: list[str] = []
    if feature.get("contract_version") != SPATIAL_CONTRACT_VERSION:
        errors.append("unsupported feature contract version")
    if feature.get("producer_repo") != producer_repo:
        errors.append("feature producer does not match owning producer")
    if feature.get("identity_semantics") != IDENTITY_DEFAULT:
        errors.append("feature identity semantics must fail closed")
    geometry = feature.get("geometry")
    if not isinstance(geometry, Mapping):
        errors.append("geometry is required")
    if not isinstance(feature.get("logical_sha256"), str):
        errors.append("logical_sha256 is required")
    if not isinstance(feature.get("source_manifestation_sha256"), str):
        errors.append("source_manifestation_sha256 is required")
    return errors


def _point(feature: Mapping[str, object]) -> tuple[float, float] | None:
    geometry = feature.get("geometry")
    if not isinstance(geometry, Mapping) or geometry.get("type") != "Point":
        return None
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, Sequence) or len(coordinates) < 2:
        return None
    lon, lat = float(coordinates[0]), float(coordinates[1])
    if not math.isfinite(lon) or not math.isfinite(lat):
        return None
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        return None
    return lon, lat


def _haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371008.8 * 2 * math.atan2(math.sqrt(h), math.sqrt(max(0.0, 1 - h)))


def cross_producer_within_distance(
    left: Iterable[Mapping[str, object]],
    right: Iterable[Mapping[str, object]],
    *,
    left_producer: str,
    right_producer: str,
    threshold_m: float,
) -> list[dict[str, object]]:
    """Return evidence-bearing candidate relations; never identity matches."""
    if left_producer == right_producer:
        raise SpatialContractError("cross-producer query requires distinct producers")
    if threshold_m < 0 or not math.isfinite(threshold_m):
        raise SpatialContractError("threshold_m must be finite and non-negative")

    left_rows = list(left)
    right_rows = list(right)
    for feature in left_rows:
        errors = validate_spatial_feature(feature, left_producer)
        if errors:
            raise SpatialContractError("; ".join(errors))
    for feature in right_rows:
        errors = validate_spatial_feature(feature, right_producer)
        if errors:
            raise SpatialContractError("; ".join(errors))

    relations: list[dict[str, object]] = []
    for a in left_rows:
        pa = _point(a)
        if pa is None:
            continue
        for b in right_rows:
            pb = _point(b)
            if pb is None:
                continue
            distance_m = _haversine_m(pa, pb)
            if distance_m <= threshold_m:
                relations.append(
                    {
                        "relation": "WITHIN_DISTANCE",
                        "left_feature_id": a.get("feature_id"),
                        "right_feature_id": b.get("feature_id"),
                        "left_producer": left_producer,
                        "right_producer": right_producer,
                        "distance_m": distance_m,
                        "threshold_m": threshold_m,
                        "method": "HUB_WGS84_GEODESIC_CONTEXT_V1",
                        "evidence_state": "COMPUTED",
                        "identity_semantics": IDENTITY_DEFAULT,
                    }
                )
    return relations


def validate_cell_id(value: object) -> list[str]:
    """Canonical, unpadded, in range. Exactly one lexical form is permitted."""
    if not isinstance(value, str) or not CELL_ID_PATTERN.match(value):
        return [f"Cell_ID {value!r} is not a canonical federation cell address"]
    row_text, _, column_text = value[1:].partition("_C")
    if int(row_text) > CELL_ROW_MAX or int(column_text) > CELL_COLUMN_MAX:
        return [f"Cell_ID {value!r} is outside the 256x384 grid"]
    return []


def validate_cell_domain_summary(summary: Mapping[str, object]) -> list[str]:
    """Producers report aggregates per cell; the Hub never ingests raw records."""
    errors = list(validate_cell_id(summary.get("Cell_ID")))

    repo = summary.get("Repository")
    if repo not in PRODUCER_REPOS:
        errors.append(f"unknown producer repository: {repo!r}")

    count = summary.get("Record_Count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        errors.append("Record_Count must be a non-negative integer")

    has_data = summary.get("Has_Data")
    if not isinstance(has_data, bool):
        errors.append("Has_Data must be a boolean")
    elif isinstance(count, int) and not isinstance(count, bool) and has_data != (count > 0):
        errors.append("Has_Data disagrees with Record_Count")

    top = summary.get("Top_Record_IDs", [])
    if not isinstance(top, Sequence) or isinstance(top, (str, bytes)):
        errors.append("Top_Record_IDs must be a list of identifiers")
    elif len(top) > 25:
        errors.append("Top_Record_IDs exceeds the 25-identifier ceiling")
    elif any(not isinstance(item, str) for item in top):
        errors.append("Top_Record_IDs must contain identifiers only, not records")

    identity = summary.get("Identity_Default", IDENTITY_DEFAULT)
    if identity != IDENTITY_DEFAULT:
        errors.append("cell co-location is candidate evidence, never identity")
    return errors


def validate_record_cell_binding_v0_2(binding: Mapping[str, object]) -> list[str]:
    """Fail closed on provisional grid bindings and preserve full candidate sets."""
    errors: list[str] = []
    state = binding.get("Certification_State")
    if state not in CERTIFICATION_STATES:
        errors.append(f"unknown Certification_State: {state!r}")
        return errors

    identity = binding.get("Identity_Default")
    if identity != IDENTITY_DEFAULT:
        errors.append("Identity_Default must be CANDIDATE_NOT_IDENTITY")

    resolution = binding.get("Resolution_State")
    cell_id_value = binding.get("Cell_ID")

    if state == "PROVISIONAL":
        if cell_id_value is not None:
            errors.append("PROVISIONAL binding must not carry an exact Cell_ID")
        if resolution != "PROVISIONAL_UNCERTAINTY_CELL_SET":
            errors.append("PROVISIONAL binding requires PROVISIONAL_UNCERTAINTY_CELL_SET")

        members = binding.get("Member_Cell_IDs")
        if not isinstance(members, Sequence) or isinstance(members, (str, bytes)) or not members:
            errors.append("PROVISIONAL binding requires non-empty Member_Cell_IDs")
        else:
            seen: set[str] = set()
            for member in members:
                member_errors = validate_cell_id(member)
                errors.extend(member_errors)
                if isinstance(member, str):
                    if member in seen:
                        errors.append(f"duplicate Member_Cell_ID: {member}")
                    seen.add(member)

        cell_set_id = binding.get("Cell_Set_ID")
        if not isinstance(cell_set_id, str) or not re.match(r"^CS_[0-9a-f]{16}$", cell_set_id):
            errors.append("PROVISIONAL binding requires canonical Cell_Set_ID")
        cell_set_sha = binding.get("Cell_Set_SHA256")
        if not isinstance(cell_set_sha, str) or not re.match(r"^[0-9a-f]{64}$", cell_set_sha):
            errors.append("PROVISIONAL binding requires Cell_Set_SHA256")

        radius = binding.get("Uncertainty_Radius_Km")
        if not isinstance(radius, (int, float)) or isinstance(radius, bool) or radius <= 0:
            errors.append("PROVISIONAL binding requires positive Uncertainty_Radius_Km")
        if binding.get("Uncertainty_Semantics") != "CONSERVATIVE_DISCOVERY_ENVELOPE_NOT_CONFIDENCE_INTERVAL":
            errors.append("PROVISIONAL binding has invalid uncertainty semantics")
        if not isinstance(binding.get("Uncertainty_Basis"), str) or not binding.get("Uncertainty_Basis"):
            errors.append("PROVISIONAL binding requires Uncertainty_Basis")
    else:
        errors.extend(validate_cell_id(cell_id_value))
        if resolution != "VERIFIED_CELL_SET":
            errors.append("VERIFIED binding requires VERIFIED_CELL_SET")
        if binding.get("Uncertainty_Radius_Km") != 0:
            errors.append("VERIFIED binding requires zero uncertainty radius")
        if binding.get("Uncertainty_Semantics") != "NONE":
            errors.append("VERIFIED binding requires NONE uncertainty semantics")

    return errors


def validate_cell_profile(profile: Mapping[str, object]) -> list[str]:
    """Same envelope from every repository; geometry never travels with it."""
    errors = list(validate_cell_id(profile.get("cell_id")))

    repo = profile.get("repository")
    if repo not in PRODUCER_REPOS:
        errors.append(f"unknown producer repository: {repo!r}")

    if not isinstance(profile.get("profile_type"), str) or not profile.get("profile_type"):
        errors.append("profile_type is required")
    if not isinstance(profile.get("summary"), Mapping):
        errors.append("summary object is required")

    state = profile.get("certification_state")
    if state is not None and state not in CERTIFICATION_STATES:
        errors.append(f"unknown certification_state: {state!r}")

    # Only the geometry authority publishes canonical geometry. A profile that
    # carries geometry would make its producer a second geometry source.
    for field in ("geometry", "coordinates", "bbox", "polygon"):
        if field in profile:
            errors.append(
                f"cell profile must not carry {field!r}; geometry stays with {GEOMETRY_AUTHORITY}"
            )
    return errors
