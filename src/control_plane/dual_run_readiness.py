"""Offline ADR 0006 H08 dual-run comparison and readiness receipts."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from ._dual_run_common import (
    DualRunReadinessError,
    as_mapping,
    receipt_path,
    replay_receipt,
    sha256_json,
    unique_index,
    validate_schema_record,
    write_json_once,
)
from ._dual_run_equivalence import compare_values, provenance_equal
from ._dual_run_receipts import (
    build_gate_evidence_projection,
    comparison_receipt_id,
    readiness_receipt_id,
)
from ._dual_run_validation import validate_dual_run_records


def _output_map(lane: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    return unique_index(lane.get("deterministic_outputs", []), "output_id", "deterministic output")


def _field_map(lane: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    return unique_index(lane.get("model_fields", []), "field_key", "model field")


def compute_dual_run_pair_comparison(
    campaign: Mapping[str, Any],
    policy: Mapping[str, Any],
    legacy_lane: Mapping[str, Any],
    candidate_lane: Mapping[str, Any],
    *,
    completed_at: str,
) -> Dict[str, Any]:
    """Purely compare one pinned legacy/candidate shadow pair."""
    reasons: List[str] = []
    if legacy_lane.get("lane") != "LEGACY_SHADOW" or candidate_lane.get("lane") != "ADR0006_CANDIDATE":
        raise DualRunReadinessError("pair lanes must be LEGACY_SHADOW and ADR0006_CANDIDATE")
    if legacy_lane.get("trial_id") != candidate_lane.get("trial_id"):
        raise DualRunReadinessError("pair trial IDs do not match")
    for key in ("campaign_id", "source_set_sha256", "pins_sha256"):
        if legacy_lane.get(key) != candidate_lane.get(key):
            reasons.append(f"PAIR_{key.upper()}_MISMATCH")
    required_outputs = set(str(item) for item in campaign.get("required_deterministic_outputs", []))
    legacy_outputs, candidate_outputs = _output_map(legacy_lane), _output_map(candidate_lane)
    output_union = set(legacy_outputs) | set(candidate_outputs) | required_outputs
    output_results: List[Dict[str, Any]] = []
    for output_id in sorted(output_union):
        left, right = legacy_outputs.get(output_id), candidate_outputs.get(output_id)
        if output_id not in required_outputs:
            status = "ADDITIONAL"
        elif left is None or right is None:
            status = "MISSING"
        elif left.get("normalized_sha256") == right.get("normalized_sha256"):
            status = "EQUAL"
        else:
            status = "UNEQUAL"
        if status != "EQUAL":
            reasons.append(f"DETERMINISTIC_{status}:{output_id}")
        output_results.append(
            {
                "output_id": output_id,
                "legacy_sha256": None if left is None else left.get("normalized_sha256"),
                "candidate_sha256": None if right is None else right.get("normalized_sha256"),
                "status": status,
            }
        )
    rules = {str(item["field_key"]): item for item in policy.get("rules", [])}
    required_fields = set(str(item) for item in campaign.get("required_model_fields", []))
    legacy_fields, candidate_fields = _field_map(legacy_lane), _field_map(candidate_lane)
    field_union = set(legacy_fields) | set(candidate_fields) | required_fields
    field_results: List[Dict[str, Any]] = []
    for field_key in sorted(field_union):
        left, right = legacy_fields.get(field_key), candidate_fields.get(field_key)
        detail: Dict[str, Any] = {}
        if field_key not in required_fields:
            status = "ADDITIONAL"
        elif left is None or right is None:
            status = "MISSING"
        elif left.get("review_status") != "REVIEWED" or right.get("review_status") != "REVIEWED":
            status = "UNRESOLVED"
        else:
            prov_equal, prov_detail = provenance_equal(
                as_mapping(left.get("provenance"), "legacy provenance"),
                as_mapping(right.get("provenance"), "candidate provenance"),
            )
            if not prov_equal:
                status = "NON_EQUIVALENT"
                detail = {"provenance_mismatches": prov_detail}
            else:
                equivalent, value_detail = compare_values(left.get("value"), right.get("value"), rules[field_key])
                status = "EQUIVALENT" if equivalent else "NON_EQUIVALENT"
                detail = value_detail
        if status != "EQUIVALENT":
            reasons.append(f"MODEL_FIELD_{status}:{field_key}")
        field_results.append(
            {
                "field_key": field_key,
                "comparator": None if field_key not in rules else rules[field_key]["comparator"],
                "legacy_value_sha256": None if left is None else sha256_json(left.get("value")),
                "candidate_value_sha256": None if right is None else sha256_json(right.get("value")),
                "status": status,
                "detail": detail,
            }
        )
    output_counts = {name: sum(item["status"] == name for item in output_results) for name in ("EQUAL", "UNEQUAL", "MISSING", "ADDITIONAL")}
    field_counts = {name: sum(item["status"] == name for item in field_results) for name in ("EQUIVALENT", "NON_EQUIVALENT", "UNRESOLVED", "MISSING", "ADDITIONAL")}
    outcome = "EQUIVALENT" if not reasons else "NON_EQUIVALENT"
    payload: Dict[str, Any] = {
        "schema_version": "dual_run_comparison_receipt.v1",
        "comparison_receipt_id": "",
        "campaign_id": campaign["campaign_id"],
        "trial_id": legacy_lane["trial_id"],
        "legacy_lane_evidence_id": legacy_lane["lane_evidence_id"],
        "candidate_lane_evidence_id": candidate_lane["lane_evidence_id"],
        "legacy_lane_sha256": sha256_json(legacy_lane),
        "candidate_lane_sha256": sha256_json(candidate_lane),
        "equivalence_policy_id": policy["policy_id"],
        "equivalence_policy_sha256": policy["policy_id"].rsplit("-", 1)[-1],
        "outcome": outcome,
        "reason_codes": sorted(set(reasons)),
        "deterministic_results": output_results,
        "deterministic_accounting": output_counts,
        "model_field_results": field_results,
        "model_field_accounting": field_counts,
        "completed_at": completed_at,
        "retirement_authorized": False,
        "certified_state_created": False,
        "active_snapshot_promoted": False,
    }
    payload["comparison_receipt_id"] = comparison_receipt_id(payload)
    return payload


def compute_campaign_readiness(
    campaign: Mapping[str, Any],
    policy: Mapping[str, Any],
    comparisons: Sequence[Mapping[str, Any]],
    rollback: Mapping[str, Any],
    lane_receipts: Sequence[Mapping[str, Any]],
    *,
    completed_at: str,
) -> Dict[str, Any]:
    """Purely aggregate pair comparisons and validated rollback evidence."""
    comparison_index = unique_index(comparisons, "trial_id", "comparison")
    expected_trials = {str(item["trial_id"]) for item in campaign["trials"]}
    reasons: List[str] = []
    if set(comparison_index) != expected_trials or len(comparison_index) < 2:
        reasons.append("INCOMPLETE_TRIAL_COMPARISON_SET")
    for trial_id, comparison in comparison_index.items():
        if comparison.get("outcome") != "EQUIVALENT":
            reasons.append(f"NON_EQUIVALENT_TRIAL:{trial_id}")
    rollback_receipt = rollback.get("execution_receipt", {})
    rollback_attested = any(
        item.get("signature_verified") is True and item.get("result") == "satisfied"
        for item in rollback.get("attestations", [])
        if isinstance(item, Mapping)
    )
    rollback_passed = (
        not rollback.get("unexpected_writes")
        and (
            (
                rollback_receipt.get("signature_verified") is True
                and rollback_receipt.get("rollback_state") == "succeeded"
                and rollback_receipt.get("status") in {"rolled_back", "succeeded"}
            )
            or rollback_attested
        )
        and bool(rollback.get("checks"))
        and all(value is True for value in rollback.get("checks", {}).values())
    )
    if not rollback_passed:
        reasons.append("ROLLBACK_EVIDENCE_NOT_VERIFIED")
    dual_status = "passed" if not any(reason.startswith(("INCOMPLETE", "NON_EQUIVALENT")) for reason in reasons) else "failed"
    overall = "READY_FOR_RETIREMENT_REVIEW" if not reasons else "BLOCKED"
    payload: Dict[str, Any] = {
        "schema_version": "dual_run_readiness_receipt.v1",
        "readiness_receipt_id": "",
        "campaign_id": campaign["campaign_id"],
        "campaign_sha256": sha256_json(campaign),
        "equivalence_policy_id": policy["policy_id"],
        "equivalence_policy_sha256": policy["policy_id"].rsplit("-", 1)[-1],
        "rollback_evidence_sha256": sha256_json(rollback),
        "comparison_receipt_ids": sorted(str(item["comparison_receipt_id"]) for item in comparisons),
        "trial_count": len(comparisons),
        "dual_run_gate_status": dual_status,
        "rollback_gate_status": "passed" if rollback_passed else "failed",
        "overall_status": overall,
        "status_reason": "; ".join(sorted(set(reasons))) if reasons else "Two equivalent trial pairs and verified rollback evidence.",
        "reason_codes": sorted(set(reasons)),
        "completed_at": completed_at,
        "retirement_authorized": False,
        "certified_state_created": False,
        "active_snapshot_promoted": False,
    }
    payload["gate_evidence"] = build_gate_evidence_projection(payload, lane_receipts, completed_at)
    payload["readiness_receipt_id"] = readiness_receipt_id(payload)
    return payload


def record_dual_run_readiness(
    storage_root: Path,
    campaign: Mapping[str, Any],
    policy: Mapping[str, Any],
    lanes: Sequence[Mapping[str, Any]],
    rollback: Mapping[str, Any],
    *,
    completed_at: str,
    schema_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Validate supplied evidence and immutably record pair/readiness receipts."""
    input_digests = {
        "campaign_sha256": sha256_json(campaign),
        "policy_sha256": sha256_json(policy),
        "lanes_sha256": sha256_json(sorted((dict(item) for item in lanes), key=lambda item: str(item.get("lane_evidence_id")))),
        "rollback_sha256": sha256_json(rollback),
    }
    path = receipt_path(Path(storage_root), str(campaign.get("campaign_id") or ""))
    replay = replay_receipt(path, input_digests)
    if replay is not None:
        return replay
    validated = validate_dual_run_records(campaign, policy, lanes, rollback, schema_dir=schema_dir)
    comparisons: List[Dict[str, Any]] = []
    for trial_id in sorted(validated["trial_lanes"]):
        trial = validated["trial_lanes"][trial_id]
        comparisons.append(
            compute_dual_run_pair_comparison(
                campaign,
                policy,
                trial["LEGACY_SHADOW"],
                trial["ADR0006_CANDIDATE"],
                completed_at=completed_at,
            )
        )
    lane_receipts = [as_mapping(item.get("execution_receipt"), "execution_receipt") for item in lanes]
    readiness = compute_campaign_readiness(
        campaign,
        policy,
        comparisons,
        rollback,
        lane_receipts,
        completed_at=completed_at,
    )
    readiness["input_digests"] = input_digests
    schema_root = validated["schema_dir"]
    for comparison in comparisons:
        validate_schema_record(
            comparison,
            "dual_run_comparison_receipt.v1.schema.json",
            schema_root,
        )
    validate_schema_record(
        readiness,
        "dual_run_readiness_receipt.v1.schema.json",
        schema_root,
    )
    validate_schema_record(
        readiness["gate_evidence"],
        "gate_evidence.schema.json",
        schema_root.parent.parent,
    )
    root = Path(storage_root)
    for comparison in comparisons:
        comparison_path = root / "registry" / "dual_run_comparisons" / f"{comparison['comparison_receipt_id']}.json"
        write_json_once(comparison_path, comparison)
    write_json_once(path, readiness)
    return readiness


__all__ = [
    "DualRunReadinessError",
    "compute_campaign_readiness",
    "compute_dual_run_pair_comparison",
    "record_dual_run_readiness",
    "validate_dual_run_records",
]
