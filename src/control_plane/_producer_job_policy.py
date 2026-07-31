"""H06 pinned policy, workspace, egress, and resource validation helpers."""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from ._producer_common import (
    _canonical_bytes, _contains_secret_material, _is_hex40, _is_sha256, _mapping, _nonempty,
    _safe_relative_path, _sha256, _string_list,
)

_ALLOWED_DECISIONS = {"ALLOW_EXTERNAL", "ALLOW_LOCAL_PRIVATE", "USE_LOCAL_PRIVATE"}

def _validate_output_contract(
    job_spec: Mapping[str, Any], reasons: List[str]
) -> Dict[str, Any]:
    contract = _mapping(job_spec.get("output_contract"))
    if set(contract) != {
        "schema_id",
        "schema_version",
        "write_root",
        "required_outputs",
    }:
        reasons.append("OUTPUT_CONTRACT_INVALID")
    required = _string_list(contract.get("required_outputs"))
    write_root = _safe_relative_path(contract.get("write_root"))
    if write_root is not None and "/" in write_root:
        write_root = None
    if (
        not _nonempty(contract.get("schema_id"))
        or not _nonempty(contract.get("schema_version"))
        or write_root is None
        or required is None
        or not required
    ):
        reasons.append("OUTPUT_CONTRACT_INVALID")
    return {
        "schema_id": contract.get("schema_id"),
        "schema_version": contract.get("schema_version"),
        "write_root": write_root,
        "required_outputs": required or [],
    }

def _validate_workspace(job_spec: Mapping[str, Any], reasons: List[str]) -> None:
    workspace = _mapping(job_spec.get("workspace_policy"))
    expected = {
        "ephemeral": True,
        "persistent_db_mounts": False,
        "skywatcher_db_access": False,
        "thehub_db_access": False,
        "secret_readback": False,
        "unrestricted_shell": False,
    }
    allowed = set(expected) | {"database_mounts", "persistent_mounts"}
    if set(workspace) != allowed:
        reasons.append("WORKSPACE_POLICY_INVALID")
    for key, value in expected.items():
        if workspace.get(key) is not value:
            reasons.append("WORKSPACE_POLICY_INVALID")
            break
    if workspace.get("database_mounts") not in ([], None):
        reasons.append("DATABASE_MOUNT_DENIED")
    if workspace.get("persistent_mounts") not in ([], None):
        reasons.append("PERSISTENT_MOUNT_DENIED")

def _validate_resources(job_spec: Mapping[str, Any], reasons: List[str]) -> Dict[str, int]:
    raw = _mapping(job_spec.get("resource_limits"))
    result: Dict[str, int] = {}
    required = {
        "max_duration_seconds",
        "max_input_bytes",
        "max_output_bytes",
        "max_output_files",
        "max_file_bytes",
    }
    if set(raw) != required:
        reasons.append("RESOURCE_LIMITS_INVALID")
    for key in sorted(required):
        value = raw.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            reasons.append("RESOURCE_LIMITS_INVALID")
            result[key] = 0
        else:
            result[key] = value
    return result

def _validate_pins(
    job_spec: Mapping[str, Any],
    expected_pins: Mapping[str, Any],
    reasons: List[str],
) -> Dict[str, Any]:
    pins = _mapping(job_spec.get("pins"))
    if set(pins) != {"worker_profile", "schema_revisions"}:
        reasons.append("PINS_INVALID")
    producer_revision = str(job_spec.get("producer_revision") or "")
    if not _is_hex40(producer_revision):
        reasons.append("PRODUCER_REVISION_INVALID")
    if producer_revision != expected_pins.get("producer_revision"):
        reasons.append("PRODUCER_REVISION_DRIFT")
    if job_spec.get("signed_command_policy_id") != expected_pins.get(
        "signed_command_policy_id"
    ):
        reasons.append("SIGNED_COMMAND_POLICY_DRIFT")
    expected_profile = _mapping(expected_pins.get("worker_profile"))
    profile = _mapping(pins.get("worker_profile"))
    if set(profile) != {"profile_id", "version", "sha256"}:
        reasons.append("WORKER_PROFILE_INVALID")
    if profile != expected_profile:
        reasons.append("WORKER_PROFILE_DRIFT")
    if (
        not _nonempty(profile.get("profile_id"))
        or not _nonempty(profile.get("version"))
        or not _is_sha256(profile.get("sha256"))
    ):
        reasons.append("WORKER_PROFILE_INVALID")
    expected_schemas = _mapping(expected_pins.get("schema_revisions"))
    schemas = _mapping(pins.get("schema_revisions"))
    if schemas != expected_schemas:
        reasons.append("SCHEMA_REVISION_DRIFT")
    if not schemas or any(not _nonempty(value) for value in schemas.values()):
        reasons.append("SCHEMA_REVISIONS_INVALID")
    return {"worker_profile": profile, "schema_revisions": schemas}

def _validate_h05_egress(
    job_spec: Mapping[str, Any],
    inputs: List[Dict[str, Any]],
    h05_egress_receipt: Optional[Mapping[str, Any]],
    reasons: List[str],
) -> bool:
    capabilities = _mapping(job_spec.get("capabilities"))
    network_requested = capabilities.get("network_access") is True
    model_operation = capabilities.get("model_operation") is True
    needs_egress = network_requested or model_operation
    reference = _mapping(job_spec.get("h05_egress_reference"))
    if not needs_egress and not reference and h05_egress_receipt is None:
        return False
    if h05_egress_receipt is None or not reference:
        reasons.append("H05_EGRESS_RECEIPT_REQUIRED")
        return False
    receipt = dict(h05_egress_receipt)
    if set(reference) != {"decision_receipt_id", "sha256"}:
        reasons.append("H05_EGRESS_REFERENCE_INVALID")
    if _contains_secret_material(receipt):
        reasons.append("H05_EGRESS_RECEIPT_SECRET_MATERIAL")
    receipt_digest = _sha256(_canonical_bytes(receipt))
    if (
        receipt.get("schema_version") != "egress_decision_receipt.v1"
        or receipt.get("allowed") is not True
        or receipt.get("decision") not in _ALLOWED_DECISIONS
    ):
        reasons.append("H05_EGRESS_RECEIPT_INVALID")
    if (
        reference.get("decision_receipt_id")
        != receipt.get("decision_receipt_id")
        or reference.get("sha256") != receipt_digest
    ):
        reasons.append("H05_EGRESS_RECEIPT_MISMATCH")
    if (
        receipt.get("authorization_reference")
        != job_spec.get("authorization_reference")
        or receipt.get("audit_event_reference")
        != job_spec.get("audit_event_reference")
    ):
        reasons.append("H05_AUTHORIZATION_REFERENCE_MISMATCH")
    artifact = _mapping(receipt.get("artifact"))
    input_ids = {item["artifact_id"] for item in inputs}
    if artifact.get("artifact_id") not in input_ids:
        reasons.append("H05_EGRESS_INPUT_MISMATCH")
    selected = _mapping(receipt.get("selected_provider"))
    if network_requested and selected.get("deployment") != "EXTERNAL":
        reasons.append("NETWORK_EXCEPTION_NOT_EXTERNAL")
    return not any(reason.startswith("H05_") for reason in reasons)

__all__ = [
    "_validate_h05_egress", "_validate_output_contract", "_validate_pins",
    "_validate_resources", "_validate_workspace",
]
