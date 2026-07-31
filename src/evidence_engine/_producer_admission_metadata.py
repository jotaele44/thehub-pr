"""H07 lineage metadata, classification, model-field, and SATIM validation."""
from __future__ import annotations

from typing import Any, List, Mapping, Sequence, Set

from ._producer_admission_common import (
    _RESTRICTION_ORDER,
    _contains_secret_material,
    _is_sha256,
    _mapping,
)


def _required_model_field_keys() -> Set[str]:
    return {
        "schema_version", "field_id", "source_artifact_id", "source_sha256",
        "model_run_receipt_id", "provider", "model", "model_revision",
        "prompt_template_version", "prompt_hash", "policy_version",
        "access_context_hash", "extraction_schema_version", "field_name", "value",
        "confidence", "validation_outcome", "review_status", "created_at",
    }


def _validate_model_fields(
    fields: Any,
    source_map: Mapping[str, Mapping[str, Any]],
    allowed_source_ids: Set[str],
) -> List[str]:
    reasons: List[str] = []
    if not isinstance(fields, list) or not fields:
        return ["MODEL_FIELD_PROVENANCE_REQUIRED"]
    seen: Set[str] = set()
    required = _required_model_field_keys()
    for raw in fields:
        field = _mapping(raw)
        field_id = str(field.get("field_id") or "")
        if not required <= set(field):
            reasons.append("MODEL_FIELD_PROVENANCE_INCOMPLETE")
        if field.get("schema_version") != "model_field_provenance.v1":
            reasons.append("MODEL_FIELD_PROVENANCE_INVALID")
        if not field_id or field_id in seen:
            reasons.append("MODEL_FIELD_ID_INVALID")
        seen.add(field_id)
        source_id = str(field.get("source_artifact_id") or "")
        source = _mapping(source_map.get(source_id))
        if source_id not in allowed_source_ids or not source:
            reasons.append("MODEL_FIELD_SOURCE_UNKNOWN")
        elif field.get("source_sha256") != source.get("sha256"):
            reasons.append("MODEL_FIELD_SOURCE_SHA_MISMATCH")
        for key in ("prompt_hash", "access_context_hash", "source_sha256"):
            if not _is_sha256(field.get(key)):
                reasons.append("MODEL_FIELD_PROVENANCE_INVALID")
        confidence = field.get("confidence")
        if confidence is not None and (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or confidence < 0
            or confidence > 1
        ):
            reasons.append("MODEL_FIELD_CONFIDENCE_INVALID")
        if _contains_secret_material(field):
            reasons.append("MODEL_FIELD_SECRET_MATERIAL")
    return sorted(set(reasons))


def _validate_satim_signal(signal: Any, allowed_source_ids: Set[str]) -> List[str]:
    value = _mapping(signal)
    required = {
        "schema_version", "signal_id", "source_artifact_ids", "method",
        "method_version", "parameters", "result", "confidence", "provisional",
        "review_status", "created_at",
    }
    reasons: List[str] = []
    if not required <= set(value):
        reasons.append("SATIM_SIGNAL_INCOMPLETE")
    if (
        value.get("schema_version") != "satim_provisional_signal.v1"
        or value.get("provisional") is not True
    ):
        reasons.append("SATIM_SIGNAL_NOT_PROVISIONAL")
    source_ids = value.get("source_artifact_ids")
    if (
        not isinstance(source_ids, list)
        or not source_ids
        or set(str(item) for item in source_ids) != allowed_source_ids
    ):
        reasons.append("SATIM_SIGNAL_SOURCE_MISMATCH")
    if _contains_secret_material(value):
        reasons.append("SATIM_SIGNAL_SECRET_MATERIAL")
    return sorted(set(reasons))


def _classification_reasons(
    output_classification: Mapping[str, Any],
    source_items: Sequence[Mapping[str, Any]],
) -> List[str]:
    reasons: List[str] = []
    classifications = [_mapping(item.get("classification")) for item in source_items]
    if not classifications or any(
        item.get("lineage_complete") is not True for item in classifications
    ):
        return ["SOURCE_CLASSIFICATION_LINEAGE_INCOMPLETE"]
    floors = [str(item.get("restriction_floor") or "") for item in classifications]
    if any(level not in _RESTRICTION_ORDER for level in floors):
        return ["SOURCE_CLASSIFICATION_INVALID"]
    inherited_floor = max(floors, key=lambda level: _RESTRICTION_ORDER[level])
    inherited_test_only = any(
        item.get("test_only") is True or item.get("level") == "TEST_ONLY"
        for item in classifications
    )
    output = _mapping(output_classification)
    if output.get("lineage_complete") is not True:
        reasons.append("OUTPUT_CLASSIFICATION_LINEAGE_INCOMPLETE")
    if output.get("restriction_floor") != inherited_floor:
        reasons.append("OUTPUT_CLASSIFICATION_FLOOR_MISMATCH")
    if output.get("test_only") is not inherited_test_only:
        reasons.append("TEST_ONLY_INHERITANCE_MISMATCH")
    level = str(output.get("level") or "")
    if inherited_test_only:
        if level != "TEST_ONLY":
            reasons.append("TEST_ONLY_INHERITANCE_MISMATCH")
    elif (
        level not in _RESTRICTION_ORDER
        or _RESTRICTION_ORDER[level] < _RESTRICTION_ORDER[inherited_floor]
    ):
        reasons.append("OUTPUT_CLASSIFICATION_DOWNGRADE")
    return sorted(set(reasons))


__all__ = ["_classification_reasons", "_validate_model_fields", "_validate_satim_signal"]
