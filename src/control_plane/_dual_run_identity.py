"""Content identities and pin-set validation for H08."""
from __future__ import annotations

from typing import Any, Dict, Mapping

from ._dual_run_common import (
    DualRunReadinessError,
    as_list,
    as_mapping,
    ensure_revision,
    ensure_sha256,
    sha256_json,
    unique_index,
)


def campaign_identity_payload(campaign: Mapping[str, Any]) -> Dict[str, Any]:
    payload = dict(campaign)
    payload.pop("campaign_id", None)
    return payload


def compute_campaign_id(campaign: Mapping[str, Any]) -> str:
    return "dual-run-campaign-sha256-" + sha256_json(campaign_identity_payload(campaign))


def compute_source_set_sha256(campaign: Mapping[str, Any]) -> str:
    records = [as_mapping(item, "source_artifact") for item in as_list(campaign.get("source_artifacts"), "source_artifacts")]
    unique_index(records, "artifact_id", "source artifact")
    normalized = sorted(
        (
            str(item["artifact_id"]),
            ensure_sha256(item["sha256"], "source artifact sha256"),
            str(item["classification"]),
        )
        for item in records
    )
    return sha256_json(normalized)


def compute_pins_sha256(campaign: Mapping[str, Any]) -> str:
    return sha256_json(as_mapping(campaign.get("pins"), "pins"))


def validate_campaign_identity(campaign: Mapping[str, Any]) -> Dict[str, str]:
    ensure_revision(campaign.get("thehub_revision"), "thehub_revision")
    ensure_revision(campaign.get("skywatcher_revision"), "skywatcher_revision")
    expected_id = compute_campaign_id(campaign)
    if campaign.get("campaign_id") != expected_id:
        raise DualRunReadinessError("campaign_id does not match canonical campaign content")
    source_set = compute_source_set_sha256(campaign)
    if campaign.get("source_set_sha256") != source_set:
        raise DualRunReadinessError("source_set_sha256 mismatch")
    pins_sha = compute_pins_sha256(campaign)
    if campaign.get("pins_sha256") != pins_sha:
        raise DualRunReadinessError("pins_sha256 mismatch")
    trials = [as_mapping(item, "trial") for item in as_list(campaign.get("trials"), "trials")]
    if len(trials) < 2:
        raise DualRunReadinessError("at least two distinct trial pairs are required")
    unique_index(trials, "trial_id", "trial")
    return {"campaign_id": expected_id, "source_set_sha256": source_set, "pins_sha256": pins_sha}


def policy_identity_payload(policy: Mapping[str, Any]) -> Dict[str, Any]:
    payload = dict(policy)
    payload.pop("policy_id", None)
    return payload


def compute_policy_id(policy: Mapping[str, Any]) -> str:
    return "model-equivalence-policy-sha256-" + sha256_json(policy_identity_payload(policy))


def validate_policy_identity(policy: Mapping[str, Any]) -> str:
    expected = compute_policy_id(policy)
    if policy.get("policy_id") != expected:
        raise DualRunReadinessError("policy_id does not match canonical policy content")
    return expected
