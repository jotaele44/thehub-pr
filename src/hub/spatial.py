"""Federation spatial-sidecar discovery and cross-producer query primitives.

The Hub is the sole cross-producer correlation authority. Producer geometry is
context/evidence only and MUST NOT establish canonical identity.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

SPATIAL_MANIFEST_VERSION = "federation-spatial-manifest/1.0"
SPATIAL_CONTRACT_VERSION = "federation-spatial-contract/1.0"
IDENTITY_DEFAULT = "CANDIDATE_NOT_IDENTITY"
HUB_AUTHORITY = "thehub-pr"


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
    if not isinstance(data, Mapping):
        raise SpatialContractError("spatial manifest must be an object")
    errors = validate_spatial_manifest(data)
    if errors:
        raise SpatialContractError("; ".join(errors))
    return SpatialProducer(
        producer_repo=str(data["producer_repo"]),
        authority=str(data["cross_repo"]["hub_correlation_authority"]),
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
    if (
        not isinstance(coordinates, Sequence)
        or isinstance(coordinates, (str, bytes))
        or len(coordinates) < 2
    ):
        return None
    if isinstance(coordinates[0], bool) or isinstance(coordinates[1], bool):
        return None
    try:
        lon, lat = float(coordinates[0]), float(coordinates[1])
    except (TypeError, ValueError):
        return None
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

    right_points = [(feature, _point(feature)) for feature in right_rows]
    relations: list[dict[str, object]] = []
    for a in left_rows:
        pa = _point(a)
        if pa is None:
            continue
        for b, pb in right_points:
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
