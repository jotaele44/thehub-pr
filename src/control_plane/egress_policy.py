"""Pure H05 egress decisions and immutable decision receipts.

This module performs no provider call, model execution, credential resolution,
retrieval, query answering, database access, or ACTIVE snapshot promotion.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from ._egress_common import (
    EgressPolicyError,
    _artifact_id,
    _canonical_bytes,
    _contains_secret_material,
    _is_sha256,
    _load_json,
    _nonempty,
    _sha256,
    _string_list,
    _write_json_once,
)
from ._egress_rules import (
    _DECISIONS,
    _classification,
    _evaluate_provider,
    _fallback_selection,
    _provider_map,
    _provider_structure_valid,
    _selection_identity,
)


def compute_egress_policy_decision(
    policy: Mapping[str, Any],
    request: Mapping[str, Any],
) -> Dict[str, Any]:
    """Return a pure deterministic allow, local-fallback, or deny decision."""
    policy_value = dict(policy) if isinstance(policy, Mapping) else {}
    request_value = dict(request) if isinstance(request, Mapping) else {}
    policy_digest = _sha256(_canonical_bytes(policy_value))
    request_digest = _sha256(_canonical_bytes(request_value))
    reasons: List[str] = []

    if (
        policy_value.get("schema_version") != "egress_policy.v1"
        or not _nonempty(policy_value.get("policy_version"))
        or not _provider_structure_valid(policy_value)
    ):
        reasons.append("POLICY_INVALID")
    if _contains_secret_material(policy_value) or _contains_secret_material(
        request_value
    ):
        reasons.append("SECRET_MATERIAL_PRESENT")

    if not _nonempty(request_value.get("request_id")):
        reasons.append("REQUEST_ID_MISSING")
    artifact = request_value.get("artifact")
    task = request_value.get("task")
    provider = request_value.get("provider")
    prompt = request_value.get("prompt_template")
    access_context = request_value.get("access_context")
    approval = request_value.get("approval", {})
    if not isinstance(artifact, Mapping):
        artifact = {}
        reasons.append("ARTIFACT_IDENTITY_INVALID")
    if not isinstance(task, Mapping):
        task = {}
        reasons.append("TASK_INVALID")
    if not isinstance(provider, Mapping):
        provider = {}
        reasons.append("PROVIDER_NOT_ALLOWLISTED")
    if not isinstance(prompt, Mapping):
        prompt = {}
        reasons.append("PROMPT_TEMPLATE_INVALID")
    if not isinstance(access_context, Mapping) or not access_context:
        access_context = {}
        reasons.append("ACCESS_CONTEXT_INVALID")
    if not isinstance(approval, Mapping):
        approval = {}

    artifact_sha = str(artifact.get("sha256") or "")
    artifact_id = str(artifact.get("artifact_id") or "")
    if not _is_sha256(artifact_sha) or artifact_id != _artifact_id(artifact_sha):
        reasons.append("ARTIFACT_IDENTITY_INVALID")
    if artifact.get("snapshot_state") != "ACTIVE":
        reasons.append("NON_ACTIVE_ARTIFACT_DENIED")

    classification, classification_reasons = _classification(artifact)
    reasons.extend(classification_reasons)

    task_type = task.get("task_type")
    purpose = task.get("purpose")
    if not _nonempty(task_type) or not _nonempty(purpose):
        reasons.append("TASK_INVALID")
    input_fields = _string_list(task.get("input_fields"))
    if input_fields is None:
        reasons.append("INPUT_FIELDS_INVALID")
    expected_fields = _string_list(task.get("expected_output_fields"))
    if expected_fields is None or not expected_fields:
        reasons.append("EXPECTED_OUTPUT_FIELDS_INVALID")

    if (
        not _nonempty(prompt.get("version"))
        or not _is_sha256(prompt.get("sha256"))
    ):
        reasons.append("PROMPT_TEMPLATE_INVALID")
    if not _nonempty(request_value.get("authorization_reference")):
        reasons.append("AUTHORIZATION_REFERENCE_MISSING")
    if not _nonempty(request_value.get("audit_event_reference")):
        reasons.append("AUDIT_EVENT_REFERENCE_MISSING")

    providers = _provider_map(policy_value)
    provider_id = str(provider.get("provider_id") or "")
    provider_policy = providers.get(provider_id)
    provider_reasons: List[str]
    if provider_policy is None:
        provider_reasons = ["PROVIDER_NOT_ALLOWLISTED"]
    else:
        provider_reasons = _evaluate_provider(
            provider_policy,
            provider,
            classification=classification,
            task=task,
            prompt=prompt,
            approval=approval,
        )
    reasons.extend(provider_reasons)
    reasons = sorted(set(reasons))

    fallback = _fallback_selection(
        policy_value,
        request_value,
        providers,
        classification=classification,
        task=task,
        prompt=prompt,
        approval=approval,
        original_reasons=reasons,
    )
    selected_provider: Optional[Dict[str, Any]]
    if not reasons:
        selected_provider = _selection_identity(provider)
        decision = (
            "ALLOW_EXTERNAL"
            if provider.get("deployment") == "EXTERNAL"
            else "ALLOW_LOCAL_PRIVATE"
        )
        allowed = True
    elif fallback is not None:
        selected_provider = _selection_identity(fallback)
        decision = "USE_LOCAL_PRIVATE"
        allowed = True
    else:
        selected_provider = None
        decision = "DENIED"
        allowed = False

    if decision not in _DECISIONS:
        raise EgressPolicyError("internal decision state is invalid")
    access_context_hash = _sha256(_canonical_bytes(dict(access_context)))
    accounting = {
        "requests": 1,
        "allowed": 1 if allowed else 0,
        "denied": 0 if allowed else 1,
        "fallback_selected": 1 if decision == "USE_LOCAL_PRIVATE" else 0,
    }
    if accounting["requests"] != accounting["allowed"] + accounting["denied"]:
        raise EgressPolicyError("egress decision accounting is incomplete")

    return {
        "schema_version": "egress_policy_decision.v1",
        "decision": decision,
        "allowed": allowed,
        "reason_codes": [] if allowed and decision != "USE_LOCAL_PRIVATE" else reasons,
        "request_digest": request_digest,
        "policy_digest": policy_digest,
        "policy_version": str(policy_value.get("policy_version") or ""),
        "access_context_sha256": access_context_hash,
        "artifact": {
            "artifact_id": artifact_id,
            "sha256": artifact_sha,
            "snapshot_state": artifact.get("snapshot_state"),
            "classification": classification,
        },
        "task": {
            "task_type": task.get("task_type"),
            "purpose": task.get("purpose"),
            "input_fields": input_fields or [],
            "expected_output_fields": expected_fields or [],
        },
        "prompt_template": {
            "version": prompt.get("version"),
            "sha256": prompt.get("sha256"),
        },
        "requested_provider": {
            "provider_id": provider.get("provider_id"),
            "deployment": provider.get("deployment"),
            "residency": provider.get("residency"),
            "model_id": provider.get("model_id"),
            "model_revision": provider.get("model_revision"),
            "credential_reference": provider.get("credential_reference"),
        },
        "selected_provider": selected_provider,
        "authorization_reference": request_value.get(
            "authorization_reference"
        ),
        "audit_event_reference": request_value.get("audit_event_reference"),
        "approval_reference": approval.get("approval_reference"),
        "accounting": accounting,
        "secret_material_serialized": False,
        "model_execution_performed": False,
        "active_snapshot_promoted": False,
        "runtime_query_answered": False,
    }


def record_egress_decision(
    storage_root: Path,
    decision_run_id: str,
    policy: Mapping[str, Any],
    request: Mapping[str, Any],
    *,
    completed_at: str,
) -> Dict[str, Any]:
    """Persist one immutable decision receipt; exact replay is idempotent."""
    run_id = decision_run_id.strip()
    if not run_id:
        raise EgressPolicyError("decision_run_id is required")
    decision = compute_egress_policy_decision(policy, request)
    run_key = _sha256(run_id.encode("utf-8"))
    receipt_path = (
        Path(storage_root)
        / "registry"
        / "egress_decisions"
        / (run_key + ".json")
    )
    if receipt_path.exists():
        existing = _load_json(receipt_path, "egress decision receipt")
        if (
            existing.get("request_digest") != decision["request_digest"]
            or existing.get("policy_digest") != decision["policy_digest"]
        ):
            raise EgressPolicyError(
                "decision_run_id already exists with different policy or request"
            )
        return existing

    receipt_identity = _sha256(
        _canonical_bytes(
            {
                "decision_run_id": run_id,
                "request_digest": decision["request_digest"],
                "policy_digest": decision["policy_digest"],
                "decision": decision["decision"],
            }
        )
    )
    receipt = dict(decision)
    receipt.update(
        {
            "schema_version": "egress_decision_receipt.v1",
            "decision_receipt_id": (
                "egress-decision-sha256-" + receipt_identity
            ),
            "decision_run_id": run_id,
            "completed_at": completed_at,
        }
    )
    if _contains_secret_material(receipt):
        raise EgressPolicyError("decision receipt contains secret material")
    _write_json_once(receipt_path, receipt)
    return receipt
