from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple

from control_plane._dual_run_common import sha256_json
from control_plane._dual_run_identity import (
    compute_campaign_id,
    compute_pins_sha256,
    compute_policy_id,
    compute_source_set_sha256,
)

THEHUB = "5" * 40
SKYWATCHER = "3b7ef00006a85c49c88bbbd129f662392fb2f370"
NOW = "2026-07-31T12:30:00Z"


def _sha(ch: str) -> str:
    return ch * 64


def policy() -> Dict[str, Any]:
    value: Dict[str, Any] = {
        "schema_version": "model_field_equivalence_policy.v1",
        "policy_id": "",
        "version": "1.0.0",
        "rules": [
            {"field_key": "registration", "comparator": "EXACT_CANONICAL", "parameters": {}},
            {"field_key": "callsign", "comparator": "NORMALIZED_TEXT_EQUAL", "parameters": {}},
            {"field_key": "tags", "comparator": "SET_EQUAL", "parameters": {}},
            {"field_key": "score", "comparator": "NUMERIC_ABSOLUTE_TOLERANCE", "parameters": {"tolerance": 0.05}},
            {"field_key": "observed_at", "comparator": "TIMESTAMP_TOLERANCE", "parameters": {"tolerance": 2.0}},
            {"field_key": "point", "comparator": "GEOSPATIAL_DISTANCE_TOLERANCE", "parameters": {"tolerance": 20.0}},
        ],
        "created_at": NOW,
    }
    value["policy_id"] = compute_policy_id(value)
    return value


def campaign(policy_value: Optional[Dict[str, Any]] = None, *, trials: int = 2) -> Dict[str, Any]:
    pol = policy_value or policy()
    value: Dict[str, Any] = {
        "schema_version": "dual_run_campaign_manifest.v1",
        "campaign_id": "",
        "thehub_revision": THEHUB,
        "skywatcher_revision": SKYWATCHER,
        "source_artifacts": [
            {"artifact_id": "artifact-sha256-" + _sha("a"), "sha256": _sha("a"), "classification": "INTERNAL"},
            {"artifact_id": "artifact-sha256-" + _sha("b"), "sha256": _sha("b"), "classification": "TEST_ONLY"},
        ],
        "source_set_sha256": "",
        "pins": {
            "schema_revisions": {
                "skywatcher_producer_package.v2": _sha("1"),
                "producer_output_lineage.v1": _sha("2"),
            },
            "provider_id": "provider-neutral",
            "model_id": "vision-model",
            "model_revision": "vision-model-2026-07",
            "prompt_template_version": "3.0.0",
            "prompt_template_hash": _sha("3"),
            "policy_version": "4.0.0",
            "policy_hash": _sha("4"),
            "worker_profile_id": "skywatcher-offline",
            "worker_profile_version": "2.0.0",
            "worker_profile_hash": _sha("5"),
            "equivalence_policy_id": pol["policy_id"],
            "equivalence_policy_sha256": pol["policy_id"].rsplit("-", 1)[-1],
        },
        "pins_sha256": "",
        "trials": [{"trial_id": f"trial-{index + 1}"} for index in range(trials)],
        "required_deterministic_outputs": ["manifest", "aviation-extractions"],
        "required_model_fields": ["registration", "callsign", "tags", "score", "observed_at", "point"],
        "production_mutation_allowed": False,
        "retirement_authorized": False,
        "created_at": NOW,
    }
    value["source_set_sha256"] = compute_source_set_sha256(value)
    value["pins_sha256"] = compute_pins_sha256(value)
    value["campaign_id"] = compute_campaign_id(value)
    return value


def provenance() -> Dict[str, Any]:
    return {
        "source_artifact_id": "artifact-sha256-" + _sha("a"),
        "source_sha256": _sha("a"),
        "provider_id": "provider-neutral",
        "model_id": "vision-model",
        "model_revision": "vision-model-2026-07",
        "prompt_template_hash": _sha("3"),
        "policy_version": "4.0.0",
        "access_context_hash": _sha("6"),
        "extraction_schema_version": "aviation_vision_extraction.v1",
    }


def _fields() -> List[Dict[str, Any]]:
    p = provenance()
    return [
        {"field_key": "registration", "value": "N12345", "provenance": copy.deepcopy(p), "review_status": "REVIEWED"},
        {"field_key": "callsign", "value": "  COAST   GUARD  ", "provenance": copy.deepcopy(p), "review_status": "REVIEWED"},
        {"field_key": "tags", "value": ["fixed-wing", "government"], "provenance": copy.deepcopy(p), "review_status": "REVIEWED"},
        {"field_key": "score", "value": 0.90, "provenance": copy.deepcopy(p), "review_status": "REVIEWED"},
        {"field_key": "observed_at", "value": "2026-07-31T12:00:00Z", "provenance": copy.deepcopy(p), "review_status": "REVIEWED"},
        {"field_key": "point", "value": {"lat": 18.45, "lon": -66.10}, "provenance": copy.deepcopy(p), "review_status": "REVIEWED"},
    ]


def lane(camp: Dict[str, Any], trial_id: str, lane_kind: str, ordinal: int) -> Dict[str, Any]:
    fields = _fields()
    if lane_kind == "ADR0006_CANDIDATE":
        next(item for item in fields if item["field_key"] == "callsign")["value"] = "coast guard"
        next(item for item in fields if item["field_key"] == "tags")["value"] = ["government", "fixed-wing"]
        next(item for item in fields if item["field_key"] == "score")["value"] = 0.92
        next(item for item in fields if item["field_key"] == "observed_at")["value"] = "2026-07-31T12:00:01Z"
        next(item for item in fields if item["field_key"] == "point")["value"] = {"lat": 18.45005, "lon": -66.10005}
    value: Dict[str, Any] = {
        "schema_version": "dual_run_lane_evidence.v1",
        "lane_evidence_id": "",
        "campaign_id": camp["campaign_id"],
        "trial_id": trial_id,
        "lane": lane_kind,
        "execution_receipt": {
            "run_id": f"{ordinal:032x}",
            "receipt_sha256": f"{ordinal:064x}",
            "signature_verified": True,
        },
        "source_set_sha256": camp["source_set_sha256"],
        "pins_sha256": camp["pins_sha256"],
        "producer_package_id": f"package-{trial_id}-{lane_kind.lower()}",
        "producer_package_sha256": _sha("7" if lane_kind == "LEGACY_SHADOW" else "8"),
        "deterministic_outputs": [
            {"output_id": "manifest", "normalized_sha256": _sha("9")},
            {"output_id": "aviation-extractions", "normalized_sha256": _sha("c")},
        ],
        "model_fields": fields,
        "schema_violations": 0,
        "missing_required_provenance": 0,
        "input_accounting": {"inputs": 2, "processed": 2, "excluded": 0, "failed": 0},
        "output_accounting": {"required": 2, "produced": 2, "failed": 0},
        "certified_state_created": False,
        "active_snapshot_promoted": False,
        "answer_eligible": False,
        "created_at": NOW,
    }
    if lane_kind == "LEGACY_SHADOW":
        value["legacy_shadow_export_id"] = f"legacy-export-{trial_id}"
    else:
        value["h06_job_record_id"] = f"h06-job-{trial_id}"
        value["h07_admission_receipt_id"] = f"h07-admission-{trial_id}"
    body = dict(value)
    body.pop("lane_evidence_id")
    value["lane_evidence_id"] = "dual-run-lane-sha256-" + sha256_json(body)
    return value


def rollback(camp: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": "rollback_drill_evidence.v1",
        "rollback_evidence_id": "rollback-drill-sha256-" + _sha("d"),
        "campaign_id": camp["campaign_id"],
        "pre_state_sha256": _sha("e"),
        "post_state_sha256": _sha("f"),
        "approved_deltas": ["candidate route disabled"],
        "failure_injection_id": "forced-candidate-failure-v1",
        "authorization_reference": "auth://rollback/1",
        "execution_receipt": {
            "run_id": "f" * 32,
            "receipt_sha256": _sha("0"),
            "signature_verified": True,
            "status": "rolled_back",
            "rollback_state": "succeeded",
        },
        "attestations": [],
        "unexpected_writes": [],
        "checks": {
            "legacy_path_restored": True,
            "candidate_path_disabled": True,
            "health_checks_passed": True,
            "immutable_evidence_preserved": True,
        },
        "logs": [{"logical_name": "rollback.log", "sha256": _sha("1")}],
        "created_at": NOW,
        "retirement_authorized": False,
    }


def valid_bundle() -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    pol = policy()
    camp = campaign(pol)
    lanes: List[Dict[str, Any]] = []
    ordinal = 1
    for trial in camp["trials"]:
        lanes.append(lane(camp, trial["trial_id"], "LEGACY_SHADOW", ordinal))
        ordinal += 1
        lanes.append(lane(camp, trial["trial_id"], "ADR0006_CANDIDATE", ordinal))
        ordinal += 1
    return camp, pol, lanes, rollback(camp)
