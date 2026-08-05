"""H06 signed-job identity, signature, and input validation helpers."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Mapping

from ._producer_common import (
    _artifact_id,
    _canonical_bytes,
    _content_locator_matches,
    _is_sha256,
    _job_identity,
    _mapping,
    _nonempty,
)

SignatureVerifier = Callable[[str, str, bytes, str], bool]
AuthorizationVerifier = Callable[[str, str, str], bool]

_ALLOWED_STATES = {"ACTIVE", "CERTIFIED", "QUARANTINED"}
_ALLOWED_WORKFLOWS = {"ACTIVE_EVIDENCE", "PROVISIONAL_PROCESSING"}
_TOP_LEVEL_FIELDS = {
    "schema_version", "job_id", "producer", "producer_revision", "operation_id",
    "signed_command_policy_id", "authorization_reference", "audit_event_reference",
    "workflow_mode", "capabilities", "h05_egress_reference", "secret_references",
    "input_artifacts", "output_contract", "pins", "workspace_policy", "network_policy",
    "resource_limits", "requested_by", "created_at", "signature",
}

def _verify_signature(
    job_spec: Mapping[str, Any],
    signature_verifier: SignatureVerifier,
    reasons: List[str],
) -> Dict[str, Any]:
    signature = _mapping(job_spec.get("signature"))
    identity = _job_identity(job_spec)
    signer_id = str(signature.get("signer_id") or "")
    scheme = str(signature.get("scheme") or "")
    value = str(signature.get("value") or "")
    payload_sha = str(signature.get("payload_sha256") or "")
    if not signature:
        reasons.append("JOB_SPEC_SIGNATURE_REQUIRED")
        return {
            "verified": False,
            "signer_id": None,
            "scheme": None,
            **identity,
        }
    if set(signature) != {"scheme", "signer_id", "payload_sha256", "value"}:
        reasons.append("JOB_SPEC_SIGNATURE_INVALID")
    if (
        not signer_id
        or not scheme
        or not value
        or payload_sha != identity["signed_payload_sha256"]
    ):
        reasons.append("JOB_SPEC_SIGNATURE_INVALID")
        return {
            "verified": False,
            "signer_id": signer_id or None,
            "scheme": scheme or None,
            **identity,
        }
    payload = _canonical_bytes(
        {key: value for key, value in job_spec.items() if key != "signature"}
    )
    try:
        verified = bool(signature_verifier(signer_id, scheme, payload, value))
    except Exception:
        reasons.append("JOB_SPEC_SIGNATURE_VERIFICATION_ERROR")
        verified = False
    if not verified:
        reasons.append("JOB_SPEC_SIGNATURE_MISMATCH")
    return {
        "verified": verified,
        "signer_id": signer_id,
        "scheme": scheme,
        **identity,
    }

def _validate_inputs(
    job_spec: Mapping[str, Any],
    resource_limits: Mapping[str, Any],
    reasons: List[str],
) -> Dict[str, Any]:
    inputs = job_spec.get("input_artifacts")
    workflow_mode = str(job_spec.get("workflow_mode") or "")
    if not isinstance(inputs, list) or not inputs:
        reasons.append("INPUT_ARTIFACTS_INVALID")
        return {"artifacts": [], "total_bytes": 0}
    normalized: List[Dict[str, Any]] = []
    identifiers: List[str] = []
    total_bytes = 0
    for raw in inputs:
        item = _mapping(raw)
        if set(item) != {
            "artifact_id",
            "sha256",
            "size_bytes",
            "read_only_locator",
            "read_only",
            "snapshot_state",
            "provisional",
            "classification",
        }:
            reasons.append("INPUT_FIELDS_INVALID")
        digest = str(item.get("sha256") or "")
        artifact_id = str(item.get("artifact_id") or "")
        size = item.get("size_bytes")
        state = str(item.get("snapshot_state") or "")
        classification = _mapping(item.get("classification"))
        if set(classification) != {
            "level",
            "restriction_floor",
            "test_only",
            "lineage_complete",
        }:
            reasons.append("INPUT_CLASSIFICATION_INVALID")
        if (
            not _is_sha256(digest)
            or artifact_id != _artifact_id(digest)
            or not _content_locator_matches(item.get("read_only_locator"), digest)
            or item.get("read_only") is not True
        ):
            reasons.append("INPUT_NOT_CONTENT_ADDRESSED")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            reasons.append("INPUT_SIZE_INVALID")
            size = 0
        total_bytes += size
        if state not in _ALLOWED_STATES:
            reasons.append("INPUT_STATE_INVALID")
        elif state != "ACTIVE" and not (
            workflow_mode == "PROVISIONAL_PROCESSING"
            and item.get("provisional") is True
        ):
            reasons.append("NON_ACTIVE_INPUT_DENIED")
        if (
            not classification
            or not _nonempty(classification.get("level"))
            or classification.get("lineage_complete") is not True
        ):
            reasons.append("INPUT_CLASSIFICATION_INVALID")
        identifiers.append(artifact_id)
        normalized.append(
            {
                "artifact_id": artifact_id,
                "sha256": digest,
                "size_bytes": size,
                "snapshot_state": state,
                "provisional": item.get("provisional") is True,
                "classification": classification,
                "read_only_locator": item.get("read_only_locator"),
            }
        )
    if len(identifiers) != len(set(identifiers)):
        reasons.append("INPUT_ARTIFACT_DUPLICATE")
    max_input = resource_limits.get("max_input_bytes")
    if isinstance(max_input, int) and not isinstance(max_input, bool):
        if total_bytes > max_input:
            reasons.append("INPUT_RESOURCE_LIMIT_EXCEEDED")
    return {"artifacts": normalized, "total_bytes": total_bytes}

__all__ = [
    "AuthorizationVerifier", "SignatureVerifier", "_ALLOWED_WORKFLOWS", "_TOP_LEVEL_FIELDS",
    "_validate_inputs", "_verify_signature",
]
