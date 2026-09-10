import json

import pytest

from hub.spatial import (
    IDENTITY_DEFAULT,
    REQUIRED_CERTIFICATION_GATES,
    SpatialContractError,
    cross_producer_within_distance,
    load_spatial_manifest,
    validate_spatial_feature,
    validate_spatial_manifest,
)


def _manifest(producer="spiderweb-pr", gate_state="OPEN"):
    return {
        "contract_version": "federation-spatial-manifest/1.0",
        "producer_repo": producer,
        "frozen_base_sha": "c" * 40,
        "authority": "test producer authority",
        "contracts": {"feature": "schemas/federation_spatial_feature.schema.json"},
        "storage": {"ownership": "REPO_LOCAL"},
        "cross_repo": {
            "identity_default": IDENTITY_DEFAULT,
            "hub_correlation_authority": "thehub-pr",
        },
        "gates": {gate: gate_state for gate in REQUIRED_CERTIFICATION_GATES},
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


def test_audit_manifest_accepts_open_gates_but_is_explicitly_non_promotable(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(_manifest(gate_state="OPEN")), encoding="utf-8")
    producer = load_spatial_manifest(path)
    assert producer.ingestion_mode == "AUDIT_ONLY"
    assert producer.promotable is False
    assert producer.authority == "test producer authority"


def test_certified_manifest_rejects_open_and_blocked_gates(tmp_path):
    manifest = _manifest(gate_state="PASS")
    manifest["gates"]["performance"] = "OPEN"
    manifest["gates"]["federation"] = "BLOCKED"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(SpatialContractError) as excinfo:
        load_spatial_manifest(path, certification=True)
    text = str(excinfo.value)
    assert "performance is OPEN" in text
    assert "federation is BLOCKED" in text


def test_certified_manifest_accepts_all_pass_and_is_promotable(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(_manifest(gate_state="PASS")), encoding="utf-8")
    producer = load_spatial_manifest(path, certification=True)
    assert producer.ingestion_mode == "CERTIFIED"
    assert producer.promotable is True


def test_certified_manifest_rejects_missing_and_unknown_gate():
    manifest = _manifest(gate_state="PASS")
    manifest["gates"].pop("security")
    manifest["gates"]["performance"] = "MAGIC"
    errors = validate_spatial_manifest(manifest, certification=True)
    assert any("missing certification gates" in error for error in errors)
    assert any("invalid gate state performance='MAGIC'" in error for error in errors)


def test_feature_rejects_wrong_producer():
    feature = _point("moneysweep-pr", "a", -66.0, 18.0)
    errors = validate_spatial_feature(feature, "spiderweb-pr")
    assert any("producer" in error for error in errors)


def test_feature_rejects_non_sha256_hash_strings():
    feature = _point("spiderweb-pr", "a", -66.0, 18.0)
    feature["logical_sha256"] = "not-a-hash"
    feature["source_manifestation_sha256"] = "A" * 64
    errors = validate_spatial_feature(feature, "spiderweb-pr")
    assert any("logical_sha256" in error for error in errors)
    assert any("source_manifestation_sha256" in error for error in errors)


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


def test_cross_producer_invalid_point_is_not_promoted_or_returned():
    left = [_point("skywatcher-pr", "flight:1", "not-a-number", 18.0)]
    right = [_point("aguayluz-pr", "asset:1", -66.0, 18.0)]
    relations = cross_producer_within_distance(
        left,
        right,
        left_producer="skywatcher-pr",
        right_producer="aguayluz-pr",
        threshold_m=100.0,
    )
    assert relations == []
