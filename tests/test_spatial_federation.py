import json

import pytest

import hub.spatial as spatial
from hub.spatial import (
    IDENTITY_DEFAULT,
    SpatialContractError,
    cross_producer_within_distance,
    load_spatial_manifest,
    validate_spatial_feature,
    validate_spatial_manifest,
)


def _manifest(producer="spiderweb-pr"):
    return {
        "contract_version": "federation-spatial-manifest/1.0",
        "producer_repo": producer,
        "contracts": {"feature": "schemas/federation_spatial_feature.schema.json"},
        "storage": {"ownership": "REPO_LOCAL"},
        "cross_repo": {
            "identity_default": IDENTITY_DEFAULT,
            "hub_correlation_authority": "thehub-pr",
        },
    }


def _point(producer, feature_id, lon, lat):
    return {
        "contract_version": "federation-spatial-contract/1.0",
        "producer_repo": producer,
        "feature_id": feature_id,
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "logical_sha256": "a" * 64,
        "source_manifestation_sha256": "b" * 64,
        "identity_semantics": IDENTITY_DEFAULT,
    }


def test_manifest_rejects_identity_promotion():
    manifest = _manifest()
    manifest["cross_repo"]["identity_default"] = "IDENTITY_MATCH"
    assert "identity_default" in " ".join(validate_spatial_manifest(manifest))


def test_loaded_manifest_uses_validated_hub_authority(tmp_path):
    path = tmp_path / "federation.spatial.json"
    path.write_text(json.dumps(_manifest()), encoding="utf-8")

    assert load_spatial_manifest(path).authority == "thehub-pr"


def test_feature_rejects_wrong_producer():
    feature = _point("moneysweep-pr", "a", -66.0, 18.0)
    errors = validate_spatial_feature(feature, "spiderweb-pr")
    assert any("producer" in error for error in errors)


def test_cross_producer_query_emits_candidate_relation_only():
    left = [_point("skywatcher-pr", "flight:1", -66.0, 18.0)]
    right = [_point("aguayluz-pr", "asset:1", -66.0001, 18.0001)]
    relations = cross_producer_within_distance(
        left,
        right,
        left_producer="skywatcher-pr",
        right_producer="aguayluz-pr",
        threshold_m=100.0,
    )
    assert len(relations) == 1
    assert relations[0]["identity_semantics"] == IDENTITY_DEFAULT
    assert relations[0]["relation"] == "WITHIN_DISTANCE"


def test_cross_producer_query_fails_closed_for_bad_feature():
    left = [_point("skywatcher-pr", "flight:1", -66.0, 18.0)]
    left[0]["identity_semantics"] = "IDENTITY_MATCH"
    right = [_point("aguayluz-pr", "asset:1", -66.0, 18.0)]
    with pytest.raises(SpatialContractError):
        cross_producer_within_distance(
            left,
            right,
            left_producer="skywatcher-pr",
            right_producer="aguayluz-pr",
            threshold_m=100.0,
        )


@pytest.mark.parametrize("coordinate", ["not-a-number", None, {}, True])
def test_cross_producer_query_skips_malformed_coordinates(coordinate):
    left = [_point("skywatcher-pr", "flight:1", coordinate, 18.0)]
    right = [_point("aguayluz-pr", "asset:1", -66.0, 18.0)]

    assert spatial._point(left[0]) is None
    assert cross_producer_within_distance(
        left,
        right,
        left_producer="skywatcher-pr",
        right_producer="aguayluz-pr",
        threshold_m=100.0,
    ) == []


def test_cross_producer_query_parses_each_right_point_once(monkeypatch):
    left = [_point("skywatcher-pr", f"flight:{i}", -66.0, 18.0) for i in range(3)]
    right = [_point("aguayluz-pr", f"asset:{i}", -66.0, 18.0) for i in range(4)]
    original = spatial._point
    calls = 0

    def counted(feature):
        nonlocal calls
        calls += 1
        return original(feature)

    monkeypatch.setattr(spatial, "_point", counted)
    cross_producer_within_distance(
        left,
        right,
        left_producer="skywatcher-pr",
        right_producer="aguayluz-pr",
        threshold_m=100.0,
    )

    assert calls == len(left) + len(right)
