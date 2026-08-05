"""Pure H05 provider, classification, minimization and fallback rules."""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ._egress_common import (
    _canonical_bytes,
    _nonempty,
    _sha256,
    _string_list,
)

_CLASSIFICATIONS = {
    "PUBLIC",
    "INTERNAL",
    "RESTRICTED",
    "SENSITIVE_LOCATION",
    "LEGAL_HOLD",
    "QUARANTINED",
    "TEST_ONLY",
}
_HIGH_RISK = {
    "RESTRICTED",
    "SENSITIVE_LOCATION",
    "LEGAL_HOLD",
    "QUARANTINED",
}
_DEPLOYMENTS = {"EXTERNAL", "LOCAL_PRIVATE"}
_DECISIONS = {
    "ALLOW_EXTERNAL",
    "ALLOW_LOCAL_PRIVATE",
    "USE_LOCAL_PRIVATE",
    "DENIED",
}


def _decision_enum_valid() -> bool:
    """Verify the closed decision vocabulary used by the public policy layer."""
    return len(_DECISIONS) == 4 and "DENIED" in _DECISIONS


_NON_FALLBACK_BLOCKERS = {
    "ACCESS_CONTEXT_INVALID",
    "ARTIFACT_IDENTITY_INVALID",
    "AUDIT_EVENT_REFERENCE_MISSING",
    "AUTHORIZATION_REFERENCE_MISSING",
    "CLASSIFICATION_INVALID",
    "CLASSIFICATION_LINEAGE_INCOMPLETE",
    "EXPECTED_OUTPUT_FIELDS_INVALID",
    "INPUT_FIELDS_INVALID",
    "NON_ACTIVE_ARTIFACT_DENIED",
    "POLICY_INVALID",
    "PROMPT_TEMPLATE_INVALID",
    "REQUEST_ID_MISSING",
    "SECRET_MATERIAL_PRESENT",
    "TASK_INVALID",
}


def _provider_map(policy: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    providers = policy.get("providers")
    if not isinstance(providers, list):
        return {}
    result: Dict[str, Dict[str, Any]] = {}
    for raw in providers:
        if not isinstance(raw, Mapping):
            continue
        provider_id = str(raw.get("provider_id") or "")
        if not provider_id or provider_id in result:
            continue
        result[provider_id] = dict(raw)
    return result


def _classification(artifact: Mapping[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    reasons: List[str] = []
    raw = artifact.get("classification")
    if not isinstance(raw, Mapping):
        return {}, ["CLASSIFICATION_INVALID"]
    level = str(raw.get("level") or "")
    floor = str(raw.get("restriction_floor") or "")
    test_only = bool(raw.get("test_only")) or level == "TEST_ONLY"
    complete = raw.get("lineage_complete") is True
    if level not in _CLASSIFICATIONS:
        reasons.append("CLASSIFICATION_INVALID")
    if floor not in _CLASSIFICATIONS - {"TEST_ONLY"}:
        reasons.append("CLASSIFICATION_INVALID")
    if not complete:
        reasons.append("CLASSIFICATION_LINEAGE_INCOMPLETE")
    return {
        "level": level,
        "restriction_floor": floor,
        "test_only": test_only,
        "lineage_complete": complete,
    }, reasons


def _exact_model_allowed(
    provider_policy: Mapping[str, Any],
    model_id: str,
    model_revision: str,
) -> bool:
    models = provider_policy.get("allowed_models")
    if not isinstance(models, list):
        return False
    for raw in models:
        if not isinstance(raw, Mapping):
            continue
        if raw.get("model_id") != model_id:
            continue
        revisions = _string_list(raw.get("revisions"))
        if revisions is not None and model_revision in revisions:
            return True
    return False


def _prompt_allowed(
    provider_policy: Mapping[str, Any],
    version: str,
    digest: str,
) -> bool:
    prompts = provider_policy.get("allowed_prompt_templates")
    if not isinstance(prompts, list):
        return False
    return any(
        isinstance(raw, Mapping)
        and raw.get("version") == version
        and raw.get("sha256") == digest
        for raw in prompts
    )


def _exact_classification_rule(
    provider_policy: Mapping[str, Any],
    classification: str,
    task_type: str,
    purpose: str,
    model_id: str,
    model_revision: str,
) -> bool:
    rules = provider_policy.get("exact_egress_rules")
    if not isinstance(rules, list):
        return False
    return any(
        isinstance(raw, Mapping)
        and raw.get("classification") == classification
        and raw.get("task_type") == task_type
        and raw.get("purpose") == purpose
        and raw.get("model_id") == model_id
        and raw.get("model_revision") == model_revision
        for raw in rules
    )


def _evaluate_provider(
    provider_policy: Mapping[str, Any],
    selection: Mapping[str, Any],
    *,
    classification: Mapping[str, Any],
    task: Mapping[str, Any],
    prompt: Mapping[str, Any],
    approval: Mapping[str, Any],
) -> List[str]:
    reasons: List[str] = []
    deployment = str(selection.get("deployment") or "")
    if deployment not in _DEPLOYMENTS:
        reasons.append("PROVIDER_DEPLOYMENT_INVALID")
    if provider_policy.get("deployment") != deployment:
        reasons.append("PROVIDER_DEPLOYMENT_MISMATCH")

    provider_id = str(selection.get("provider_id") or "")
    if provider_policy.get("provider_id") != provider_id:
        reasons.append("PROVIDER_NOT_ALLOWLISTED")

    model_id = str(selection.get("model_id") or "")
    model_revision = str(selection.get("model_revision") or "")
    if not model_id:
        reasons.append("MODEL_ID_MISSING")
    if not model_revision:
        reasons.append("MODEL_REVISION_MISSING")
    if model_id and model_revision and not _exact_model_allowed(
        provider_policy, model_id, model_revision
    ):
        reasons.append("MODEL_REVISION_NOT_ALLOWLISTED")

    residency = str(selection.get("residency") or "")
    residencies = _string_list(provider_policy.get("residencies"))
    if residencies is None or residency not in residencies:
        reasons.append("PROVIDER_RESIDENCY_MISMATCH")

    purpose = str(task.get("purpose") or "")
    task_type = str(task.get("task_type") or "")
    permitted_uses = _string_list(provider_policy.get("permitted_uses"))
    task_types = _string_list(provider_policy.get("task_types"))
    if permitted_uses is None or purpose not in permitted_uses:
        reasons.append("PURPOSE_NOT_PERMITTED")
    if task_types is None or task_type not in task_types:
        reasons.append("TASK_TYPE_NOT_PERMITTED")
    if selection.get("permitted_use") != purpose:
        reasons.append("PROVIDER_PERMITTED_USE_MISMATCH")

    prompt_version = str(prompt.get("version") or "")
    prompt_sha = str(prompt.get("sha256") or "")
    if not _prompt_allowed(
        provider_policy,
        prompt_version,
        prompt_sha,
    ):
        reasons.append("PROMPT_TEMPLATE_NOT_ALLOWLISTED")

    level = str(classification.get("level") or "")
    floor = str(classification.get("restriction_floor") or "")
    policy_classification = floor if level == "TEST_ONLY" else level
    allowed_classifications = _string_list(
        provider_policy.get("allowed_classifications")
    )
    if (
        allowed_classifications is None
        or policy_classification not in allowed_classifications
    ):
        reasons.append("CLASSIFICATION_NOT_EXACTLY_ALLOWED")
    if (
        deployment == "EXTERNAL"
        and policy_classification in _HIGH_RISK
        and not _exact_classification_rule(
            provider_policy,
            policy_classification,
            task_type,
            purpose,
            model_id,
            model_revision,
        )
    ):
        reasons.append("EXACT_CLASSIFICATION_POLICY_MISSING")
    if deployment == "EXTERNAL" and bool(classification.get("test_only")):
        reasons.append("TEST_ONLY_EXTERNAL_EGRESS_DENIED")

    approval_required = _string_list(
        provider_policy.get("approval_required_for")
    )
    if approval_required is None:
        reasons.append("PROVIDER_POLICY_INVALID")
    elif policy_classification in approval_required:
        if (
            approval.get("state") != "APPROVED"
            or not _nonempty(approval.get("approval_reference"))
        ):
            reasons.append("APPROVAL_REQUIRED")

    requested_fields = _string_list(task.get("input_fields"))
    allowed_fields = _string_list(provider_policy.get("allowed_input_fields"))
    required_fields = _string_list(
        provider_policy.get("required_input_fields")
    )
    if requested_fields is None:
        reasons.append("INPUT_FIELDS_INVALID")
    elif allowed_fields is None or not set(requested_fields) <= set(
        allowed_fields
    ):
        reasons.append("DATA_MINIMIZATION_REQUIRED")
    elif required_fields is None or not set(required_fields) <= set(
        requested_fields
    ):
        reasons.append("REQUIRED_INPUT_FIELD_MISSING")

    credential_reference = selection.get("credential_reference")
    allowed_credentials = provider_policy.get("credential_references")
    if not isinstance(allowed_credentials, list):
        reasons.append("CREDENTIAL_REFERENCE_NOT_ALLOWLISTED")
    elif credential_reference not in allowed_credentials:
        reasons.append("CREDENTIAL_REFERENCE_NOT_ALLOWLISTED")

    return reasons


def _selection_identity(selection: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "provider_id": selection.get("provider_id"),
        "deployment": selection.get("deployment"),
        "residency": selection.get("residency"),
        "permitted_use": selection.get("permitted_use"),
        "model_id": selection.get("model_id"),
        "model_revision": selection.get("model_revision"),
        "credential_reference": selection.get("credential_reference"),
    }


def _fallback_selection(
    policy: Mapping[str, Any],
    request: Mapping[str, Any],
    providers: Mapping[str, Dict[str, Any]],
    *,
    classification: Mapping[str, Any],
    task: Mapping[str, Any],
    prompt: Mapping[str, Any],
    approval: Mapping[str, Any],
    original_reasons: Sequence[str],
) -> Optional[Dict[str, Any]]:
    if set(original_reasons) & _NON_FALLBACK_BLOCKERS:
        return None
    requested_provider = request.get("provider")
    if not isinstance(requested_provider, Mapping):
        return None
    if requested_provider.get("deployment") != "EXTERNAL":
        return None
    fallbacks = policy.get("fallbacks")
    if not isinstance(fallbacks, list):
        return None

    level = str(classification.get("level") or "")
    floor = str(classification.get("restriction_floor") or "")
    policy_classification = floor if level == "TEST_ONLY" else level
    candidates: List[Tuple[int, str, Dict[str, Any]]] = []
    for raw in fallbacks:
        if not isinstance(raw, Mapping):
            continue
        if raw.get("from_provider_id") != requested_provider.get("provider_id"):
            continue
        if raw.get("task_type") != task.get("task_type"):
            continue
        if raw.get("purpose") != task.get("purpose"):
            continue
        classes = _string_list(raw.get("classifications"))
        if classes is None or policy_classification not in classes:
            continue
        selection = {
            "provider_id": raw.get("provider_id"),
            "deployment": "LOCAL_PRIVATE",
            "residency": raw.get("residency"),
            "permitted_use": task.get("purpose"),
            "model_id": raw.get("model_id"),
            "model_revision": raw.get("model_revision"),
            "credential_reference": raw.get("credential_reference"),
        }
        provider_id = str(selection.get("provider_id") or "")
        provider_policy = providers.get(provider_id)
        if provider_policy is None:
            continue
        reasons = _evaluate_provider(
            provider_policy,
            selection,
            classification=classification,
            task=task,
            prompt=prompt,
            approval=approval,
        )
        if reasons:
            continue
        priority = raw.get("priority", 100)
        try:
            priority_value = int(priority)
        except (TypeError, ValueError):
            priority_value = 100
        candidates.append(
            (
                priority_value,
                _sha256(_canonical_bytes(selection)),
                selection,
            )
        )
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def _provider_structure_valid(policy: Mapping[str, Any]) -> bool:
    if not _decision_enum_valid():
        return False
    providers = policy.get("providers")
    if not isinstance(providers, list) or not providers:
        return False
    identifiers: List[str] = []
    for raw in providers:
        if not isinstance(raw, Mapping):
            return False
        provider_id = str(raw.get("provider_id") or "")
        if not provider_id:
            return False
        identifiers.append(provider_id)
    return len(identifiers) == len(set(identifiers))
