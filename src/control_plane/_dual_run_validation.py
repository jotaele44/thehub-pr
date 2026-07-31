"""Schema and accounting validation for H08 evidence records."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from ._dual_run_common import (
    DualRunReadinessError,
    as_list,
    as_mapping,
    ensure_sha256,
    schema_directory,
    unique_index,
    validate_schema_record,
)
from ._dual_run_equivalence import validate_policy_rules
from ._dual_run_identity import validate_campaign_identity, validate_policy_identity

_SCHEMA_FILES = {
    "dual_run_campaign_manifest.v1": "dual_run_campaign_manifest.v1.schema.json",
    "model_field_equivalence_policy.v1": "model_field_equivalence_policy.v1.schema.json",
    "dual_run_lane_evidence.v1": "dual_run_lane_evidence.v1.schema.json",
    "dual_run_comparison_receipt.v1": "dual_run_comparison_receipt.v1.schema.json",
    "dual_run_readiness_receipt.v1": "dual_run_readiness_receipt.v1.schema.json",
    "rollback_drill_evidence.v1": "rollback_drill_evidence.v1.schema.json",
}


def _accounting_complete(accounting: Mapping[str, Any], *, output: bool = False) -> bool:
    if output:
        return int(accounting.get("required", -1)) == int(accounting.get("produced", -2)) + int(accounting.get("failed", -3))
    return int(accounting.get("inputs", -1)) == int(accounting.get("processed", -2)) + int(accounting.get("excluded", -3)) + int(accounting.get("failed", -4))


def validate_lane_accounting(lane: Mapping[str, Any]) -> None:
    if not _accounting_complete(as_mapping(lane.get("input_accounting"), "input_accounting")):
        raise DualRunReadinessError("incomplete lane input accounting")
    if not _accounting_complete(as_mapping(lane.get("output_accounting"), "output_accounting"), output=True):
        raise DualRunReadinessError("incomplete lane output accounting")
    if int(lane.get("schema_violations", -1)) != 0:
        raise DualRunReadinessError("schema violations block dual-run readiness")
    if int(lane.get("missing_required_provenance", -1)) != 0:
        raise DualRunReadinessError("missing required provenance blocks dual-run readiness")
    receipt = as_mapping(lane.get("execution_receipt"), "execution_receipt")
    if receipt.get("signature_verified") is not True:
        raise DualRunReadinessError("execution receipt must be signature verified")
    ensure_sha256(receipt.get("receipt_sha256"), "execution receipt sha256")
    lane_kind = lane.get("lane")
    if lane_kind == "ADR0006_CANDIDATE":
        for key in ("h06_job_record_id", "h07_admission_receipt_id"):
            if not lane.get(key):
                raise DualRunReadinessError(f"candidate lane requires {key}")
    elif lane_kind == "LEGACY_SHADOW":
        if not lane.get("legacy_shadow_export_id"):
            raise DualRunReadinessError("legacy lane requires legacy_shadow_export_id")
    else:
        raise DualRunReadinessError("unsupported dual-run lane")


def validate_rollback_evidence(rollback: Mapping[str, Any], schema_dir: Path) -> None:
    validate_schema_record(rollback, _SCHEMA_FILES["rollback_drill_evidence.v1"], schema_dir)
    receipt = as_mapping(rollback.get("execution_receipt"), "rollback execution receipt")
    attestations = as_list(rollback.get("attestations", []), "attestations")
    receipt_valid = (
        receipt.get("signature_verified") is True
        and receipt.get("rollback_state") == "succeeded"
        and receipt.get("status") in {"rolled_back", "succeeded"}
    )
    attestation_valid = any(
        as_mapping(item, "attestation").get("signature_verified") is True
        and as_mapping(item, "attestation").get("result") == "satisfied"
        for item in attestations
    )
    if not receipt_valid and not attestation_valid:
        raise DualRunReadinessError("rollback pass requires verified receipt or attestation")
    if rollback.get("unexpected_writes"):
        raise DualRunReadinessError("unexpected rollback writes block readiness")
    checks = as_mapping(rollback.get("checks"), "rollback checks")
    if not checks or not all(value is True for value in checks.values()):
        raise DualRunReadinessError("rollback functional and preservation checks must pass")


def validate_dual_run_records(
    campaign: Mapping[str, Any],
    policy: Mapping[str, Any],
    lanes: Sequence[Mapping[str, Any]],
    rollback: Mapping[str, Any],
    *,
    schema_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    root = schema_directory(Path(__file__), schema_dir)
    validate_schema_record(campaign, _SCHEMA_FILES["dual_run_campaign_manifest.v1"], root)
    validate_schema_record(policy, _SCHEMA_FILES["model_field_equivalence_policy.v1"], root)
    for lane in lanes:
        validate_schema_record(lane, _SCHEMA_FILES["dual_run_lane_evidence.v1"], root)
    identity = validate_campaign_identity(campaign)
    policy_id = validate_policy_identity(policy)
    pins = as_mapping(campaign.get("pins"), "pins")
    if pins.get("equivalence_policy_id") != policy_id:
        raise DualRunReadinessError("campaign equivalence policy reference mismatch")
    if pins.get("equivalence_policy_sha256") != policy_id.rsplit("-", 1)[-1]:
        raise DualRunReadinessError("campaign equivalence policy sha mismatch")
    required_fields = [str(item) for item in as_list(campaign.get("required_model_fields"), "required_model_fields")]
    rules = validate_policy_rules(policy, required_fields)
    lane_index = unique_index(lanes, "lane_evidence_id", "lane evidence")
    execution_ids: Dict[str, str] = {}
    trial_lanes: Dict[str, Dict[str, Mapping[str, Any]]] = {}
    for lane in lanes:
        validate_lane_accounting(lane)
        if lane.get("campaign_id") != campaign.get("campaign_id"):
            raise DualRunReadinessError("lane campaign binding mismatch")
        if lane.get("source_set_sha256") != identity["source_set_sha256"]:
            raise DualRunReadinessError("source set drift denied")
        if lane.get("pins_sha256") != identity["pins_sha256"]:
            raise DualRunReadinessError("pin-set drift denied")
        receipt = as_mapping(lane.get("execution_receipt"), "execution_receipt")
        run_id = str(receipt.get("run_id") or "")
        if run_id in execution_ids:
            raise DualRunReadinessError("duplicated execution receipt denied")
        execution_ids[run_id] = str(lane["lane_evidence_id"])
        trial = trial_lanes.setdefault(str(lane["trial_id"]), {})
        lane_kind = str(lane["lane"])
        if lane_kind in trial:
            raise DualRunReadinessError("duplicate lane within trial")
        trial[lane_kind] = lane
    expected_trials = {str(as_mapping(item, "trial")["trial_id"]) for item in campaign["trials"]}
    if set(trial_lanes) != expected_trials:
        raise DualRunReadinessError("lane evidence does not cover exact campaign trials")
    for trial_id, trial in trial_lanes.items():
        if set(trial) != {"LEGACY_SHADOW", "ADR0006_CANDIDATE"}:
            raise DualRunReadinessError(f"trial {trial_id} requires exactly two dual-run lanes")
    validate_rollback_evidence(rollback, root)
    if rollback.get("campaign_id") != campaign.get("campaign_id"):
        raise DualRunReadinessError("rollback campaign binding mismatch")
    return {
        "schema_dir": root,
        "identity": identity,
        "policy_id": policy_id,
        "rules": rules,
        "lane_index": lane_index,
        "trial_lanes": trial_lanes,
        "execution_ids": execution_ids,
    }
