"""H06 signed bounded-producer job validation without launching a worker."""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from ._producer_common import (
    _contains_secret_material, _job_identity, _mapping, _nonempty, _string_list,
)
from ._producer_job_identity import (
    AuthorizationVerifier, SignatureVerifier, _ALLOWED_WORKFLOWS, _TOP_LEVEL_FIELDS,
    _validate_inputs, _verify_signature,
)
from ._producer_job_policy import (
    _validate_h05_egress, _validate_output_contract, _validate_pins,
    _validate_resources, _validate_workspace,
)

def compute_bounded_producer_job_decision(
    job_spec: Mapping[str, Any],
    expected_pins: Mapping[str, Any],
    *,
    signature_verifier: SignatureVerifier,
    authorization_verifier: AuthorizationVerifier,
    h05_egress_receipt: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate one signed job specification without launching any worker."""
    spec = dict(job_spec) if isinstance(job_spec, Mapping) else {}
    expected = dict(expected_pins) if isinstance(expected_pins, Mapping) else {}
    reasons: List[str] = []
    identity = _job_identity(spec)

    unknown_fields = set(spec) - _TOP_LEVEL_FIELDS
    missing_fields = (_TOP_LEVEL_FIELDS - {"h05_egress_reference"}) - set(spec)
    if unknown_fields or missing_fields:
        reasons.append("JOB_SPEC_FIELDS_INVALID")
    if spec.get("schema_version") != "bounded_producer_job.v2":
        reasons.append("JOB_SPEC_SCHEMA_INVALID")
    if spec.get("job_id") != identity["job_spec_id"]:
        reasons.append("JOB_SPEC_ID_MISMATCH")
    if spec.get("producer") != "skywatcher-pr":
        reasons.append("PRODUCER_INVALID")
    if not _nonempty(spec.get("operation_id")):
        reasons.append("OPERATION_ID_REQUIRED")
    if spec.get("workflow_mode") not in _ALLOWED_WORKFLOWS:
        reasons.append("WORKFLOW_MODE_INVALID")
    if not _nonempty(spec.get("requested_by")) or not _nonempty(
        spec.get("created_at")
    ):
        reasons.append("REQUEST_METADATA_INVALID")

    if _contains_secret_material(spec):
        reasons.append("SECRET_VALUE_PRESENT")
    secret_refs = _string_list(spec.get("secret_references"))
    if secret_refs is None or any(
        not reference.startswith("secret://") for reference in secret_refs
    ):
        reasons.append("SECRET_REFERENCES_INVALID")

    signature = _verify_signature(spec, signature_verifier, reasons)
    authorization_reference = str(spec.get("authorization_reference") or "")
    audit_reference = str(spec.get("audit_event_reference") or "")
    if not authorization_reference:
        reasons.append("AUTHORIZATION_REFERENCE_REQUIRED")
    if not audit_reference:
        reasons.append("AUDIT_EVENT_REFERENCE_REQUIRED")
    authorization_verified = False
    if authorization_reference and audit_reference:
        try:
            authorization_verified = bool(
                authorization_verifier(
                    authorization_reference,
                    audit_reference,
                    identity["job_identity_sha256"],
                )
            )
        except Exception:
            reasons.append("AUTHORIZATION_VERIFICATION_ERROR")
        if not authorization_verified:
            reasons.append("AUTHORIZATION_VERIFICATION_FAILED")

    pins = _validate_pins(spec, expected, reasons)
    resource_limits = _validate_resources(spec, reasons)
    inputs = _validate_inputs(spec, resource_limits, reasons)
    output_contract = _validate_output_contract(spec, reasons)
    _validate_workspace(spec, reasons)

    capabilities = _mapping(spec.get("capabilities"))
    if set(capabilities) != {"network_access", "model_operation"} or any(
        not isinstance(value, bool) for value in capabilities.values()
    ):
        reasons.append("CAPABILITIES_INVALID")
    network = _mapping(spec.get("network_policy"))
    allowed_network_fields = {
        "default",
        "approved_hosts",
        "max_requests",
        "exception_authorization_reference",
    }
    required_network_fields = {"default", "approved_hosts", "max_requests"}
    if set(network) - allowed_network_fields or not required_network_fields <= set(network):
        reasons.append("NETWORK_POLICY_INVALID")
    if network.get("default") != "DENY":
        reasons.append("NETWORK_DEFAULT_DENY_REQUIRED")
    hosts = _string_list(network.get("approved_hosts"))
    max_requests = network.get("max_requests")
    network_requested = capabilities.get("network_access") is True
    if hosts is not None and any(
        "://" in host or "/" in host or "\\" in host for host in hosts
    ):
        reasons.append("NETWORK_EXCEPTION_HOST_INVALID")
    if network_requested:
        if hosts is None or not hosts:
            reasons.append("NETWORK_EXCEPTION_HOSTS_REQUIRED")
        if (
            not isinstance(max_requests, int)
            or isinstance(max_requests, bool)
            or max_requests <= 0
        ):
            reasons.append("NETWORK_EXCEPTION_LIMIT_INVALID")
        if network.get("exception_authorization_reference") != authorization_reference:
            reasons.append("NETWORK_EXCEPTION_UNAUTHORIZED")
    else:
        if hosts not in ([], None) or max_requests not in (0, None):
            reasons.append("UNAUTHORIZED_NETWORK_REQUEST")
        if network.get("exception_authorization_reference") not in (None, ""):
            reasons.append("UNAUTHORIZED_NETWORK_REQUEST")

    egress_verified = _validate_h05_egress(
        spec,
        inputs["artifacts"],
        h05_egress_receipt,
        reasons,
    )
    reasons = sorted(set(reasons))
    accepted = not reasons
    return {
        "schema_version": "bounded_producer_job_decision.v1",
        "decision": "ACCEPTED" if accepted else "DENIED",
        "accepted": accepted,
        "reason_codes": reasons,
        "job_spec_id": identity["job_spec_id"],
        "job_identity_sha256": identity["job_identity_sha256"],
        "signed_payload_sha256": identity["signed_payload_sha256"],
        "signature": {
            "verified": signature["verified"],
            "signer_id": signature["signer_id"],
            "scheme": signature["scheme"],
        },
        "authorization_verified": authorization_verified,
        "egress_verified": egress_verified,
        "producer_revision": spec.get("producer_revision"),
        "workflow_mode": spec.get("workflow_mode"),
        "pins": pins,
        "inputs": inputs,
        "output_contract": output_contract,
        "resource_limits": resource_limits,
        "capabilities": capabilities,
        "network_policy": {
            "default": network.get("default"),
            "approved_hosts": hosts or [],
            "max_requests": max_requests or 0,
        },
        "authorization_reference": spec.get("authorization_reference"),
        "audit_event_reference": spec.get("audit_event_reference"),
        "secret_material_serialized": False,
        "worker_execution_performed": False,
        "model_execution_performed": False,
        "active_snapshot_promoted": False,
        "runtime_query_answered": False,
    }

__all__ = [
    "AuthorizationVerifier", "SignatureVerifier", "compute_bounded_producer_job_decision",
]
