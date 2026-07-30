"""Immutable H05 model-run receipts and field provenance.

This module records supplied outcomes only. It never executes or contacts a model.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from ._egress_common import (
    EgressPolicyError,
    _canonical_bytes,
    _contains_secret_material,
    _load_json,
    _nonempty,
    _safe_write_once,
    _sha256,
    _string_list,
    _write_json_once,
)

_VALIDATION_OUTCOMES = {"VALID", "INVALID", "UNVERIFIED", "CONFLICTED"}
_REVIEW_STATES = {
    "UNREVIEWED",
    "NEEDS_REVIEW",
    "APPROVED",
    "REJECTED",
    "SUPERSEDED",
}


def _field_record(
    *,
    model_run_receipt_id: str,
    egress_receipt: Mapping[str, Any],
    extraction_schema_version: str,
    field: Mapping[str, Any],
) -> Dict[str, Any]:
    field_name = str(field.get("field_name") or "")
    if not field_name:
        raise EgressPolicyError("every field result requires field_name")
    confidence = field.get("confidence")
    if confidence is not None and (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or confidence < 0
        or confidence > 1
    ):
        raise EgressPolicyError("field confidence must be between 0 and 1")
    validation_outcome = str(field.get("validation_outcome") or "")
    review_status = str(field.get("review_status") or "")
    if validation_outcome not in _VALIDATION_OUTCOMES:
        raise EgressPolicyError("field validation_outcome is invalid")
    if review_status not in _REVIEW_STATES:
        raise EgressPolicyError("field review_status is invalid")
    if not _nonempty(field.get("created_at")):
        raise EgressPolicyError("field created_at is required")

    provider = egress_receipt.get("selected_provider")
    artifact = egress_receipt.get("artifact")
    prompt = egress_receipt.get("prompt_template")
    if not isinstance(provider, Mapping):
        raise EgressPolicyError("authorized provider identity is unavailable")
    if not isinstance(artifact, Mapping):
        raise EgressPolicyError("source artifact identity is unavailable")
    if not isinstance(prompt, Mapping):
        raise EgressPolicyError("prompt identity is unavailable")

    identity = {
        "model_run_receipt_id": model_run_receipt_id,
        "field_name": field_name,
        "value": field.get("value"),
        "source_region": field.get("source_region"),
        "supersedes_field_id": field.get("supersedes_field_id"),
    }
    field_id = "model-field-sha256-" + _sha256(_canonical_bytes(identity))
    return {
        "schema_version": "model_field_provenance.v1",
        "field_id": field_id,
        "source_artifact_id": artifact.get("artifact_id"),
        "source_sha256": artifact.get("sha256"),
        "source_region": field.get("source_region"),
        "model_run_receipt_id": model_run_receipt_id,
        "provider": provider.get("provider_id"),
        "model": provider.get("model_id"),
        "model_revision": provider.get("model_revision"),
        "prompt_template_version": prompt.get("version"),
        "prompt_hash": prompt.get("sha256"),
        "policy_version": egress_receipt.get("policy_version"),
        "access_context_hash": egress_receipt.get("access_context_sha256"),
        "extraction_schema_version": extraction_schema_version,
        "field_name": field_name,
        "value": field.get("value"),
        "confidence": confidence,
        "validation_outcome": validation_outcome,
        "review_status": review_status,
        "reviewer_id": field.get("reviewer_id"),
        "created_at": field.get("created_at"),
        "supersedes_field_id": field.get("supersedes_field_id"),
    }


def record_model_run_receipt(
    storage_root: Path,
    model_run_id: str,
    egress_decision_receipt: Mapping[str, Any],
    field_results: Iterable[Mapping[str, Any]],
    field_failures: Iterable[Mapping[str, Any]],
    *,
    extraction_schema_version: str,
    completed_at: str,
) -> Dict[str, Any]:
    """Record supplied model outcomes without executing or contacting a model."""
    run_id = model_run_id.strip()
    if not run_id:
        raise EgressPolicyError("model_run_id is required")
    if not extraction_schema_version.strip():
        raise EgressPolicyError("extraction_schema_version is required")
    egress = dict(egress_decision_receipt)
    if egress.get("schema_version") != "egress_decision_receipt.v1":
        raise EgressPolicyError("egress decision receipt schema is invalid")
    if egress.get("allowed") is not True:
        raise EgressPolicyError("model run cannot use a denied egress decision")
    if egress.get("decision") not in {
        "ALLOW_EXTERNAL",
        "ALLOW_LOCAL_PRIVATE",
        "USE_LOCAL_PRIVATE",
    }:
        raise EgressPolicyError("egress decision is not executable")
    artifact = egress.get("artifact")
    if (
        not isinstance(artifact, Mapping)
        or artifact.get("snapshot_state") != "ACTIVE"
    ):
        raise EgressPolicyError("non-ACTIVE artifact cannot enter model context")
    if _contains_secret_material(egress):
        raise EgressPolicyError("egress receipt contains secret material")

    results = [dict(item) for item in field_results]
    failures = [dict(item) for item in field_failures]
    if _contains_secret_material(results) or _contains_secret_material(failures):
        raise EgressPolicyError("model result contains secret material")

    task = egress.get("task")
    if not isinstance(task, Mapping):
        raise EgressPolicyError("egress task identity is unavailable")
    expected = _string_list(task.get("expected_output_fields"))
    if expected is None or not expected:
        raise EgressPolicyError("expected output fields are invalid")

    result_names = [str(item.get("field_name") or "") for item in results]
    failure_names = [str(item.get("field_name") or "") for item in failures]
    if (
        any(not name for name in result_names + failure_names)
        or len(result_names) != len(set(result_names))
        or len(failure_names) != len(set(failure_names))
        or set(result_names) & set(failure_names)
        or set(expected) != set(result_names) | set(failure_names)
    ):
        raise EgressPolicyError(
            "model field accounting does not partition expected outputs"
        )
    for failure in failures:
        if not _nonempty(failure.get("failure_code")):
            raise EgressPolicyError("field failure requires failure_code")

    run_key = _sha256(run_id.encode("utf-8"))
    receipt_id = "model-run-sha256-" + run_key
    records = [
        _field_record(
            model_run_receipt_id=receipt_id,
            egress_receipt=egress,
            extraction_schema_version=extraction_schema_version,
            field=field,
        )
        for field in results
    ]
    records.sort(key=lambda item: str(item["field_name"]))
    failures.sort(key=lambda item: str(item["field_name"]))

    output_manifest_digest = _sha256(
        _canonical_bytes(
            {
                "records": records,
                "failures": failures,
                "extraction_schema_version": extraction_schema_version,
            }
        )
    )
    root = Path(storage_root)
    receipt_path = root / "registry" / "model_runs" / (run_key + ".json")
    egress_digest = _sha256(_canonical_bytes(egress))
    if receipt_path.exists():
        existing = _load_json(receipt_path, "model run receipt")
        if (
            existing.get("egress_decision_digest") != egress_digest
            or existing.get("output_manifest_digest")
            != output_manifest_digest
        ):
            raise EgressPolicyError(
                "model_run_id already exists with different inputs or outputs"
            )
        return existing

    provenance_refs: List[Dict[str, Any]] = []
    for record in records:
        record_bytes = _canonical_bytes(record) + b"\n"
        record_digest = _sha256(record_bytes)
        field_key = str(record["field_id"]).removeprefix(
            "model-field-sha256-"
        )
        record_path = (
            root
            / "registry"
            / "model_field_provenance"
            / field_key[:2]
            / (field_key + ".json")
        )
        _safe_write_once(record_path, record_bytes)
        provenance_refs.append(
            {
                "field_id": record["field_id"],
                "field_name": record["field_name"],
                "record_sha256": record_digest,
                "locator": record_path.relative_to(root).as_posix(),
            }
        )

    if not results:
        outcome = "FAILED"
    elif failures:
        outcome = "PARTIAL"
    else:
        outcome = "SUCCEEDED"
    selected_provider = egress.get("selected_provider")
    prompt = egress.get("prompt_template")
    if not isinstance(selected_provider, Mapping) or not isinstance(
        prompt, Mapping
    ):
        raise EgressPolicyError("egress receipt lacks immutable identities")
    accounting = {
        "expected_fields": len(expected),
        "output_fields": len(records),
        "failed_fields": len(failures),
    }
    if accounting["expected_fields"] != (
        accounting["output_fields"] + accounting["failed_fields"]
    ):
        raise EgressPolicyError("model run accounting is incomplete")

    receipt = {
        "schema_version": "model_run_receipt.v1",
        "model_run_receipt_id": receipt_id,
        "model_run_id": run_id,
        "egress_decision_receipt_id": egress.get("decision_receipt_id"),
        "egress_decision_digest": egress_digest,
        "output_manifest_digest": output_manifest_digest,
        "outcome": outcome,
        "source_artifact_id": artifact.get("artifact_id"),
        "source_sha256": artifact.get("sha256"),
        "provider": selected_provider.get("provider_id"),
        "provider_deployment": selected_provider.get("deployment"),
        "provider_residency": selected_provider.get("residency"),
        "model": selected_provider.get("model_id"),
        "model_revision": selected_provider.get("model_revision"),
        "credential_reference": selected_provider.get(
            "credential_reference"
        ),
        "prompt_template_version": prompt.get("version"),
        "prompt_template_sha256": prompt.get("sha256"),
        "policy_version": egress.get("policy_version"),
        "access_context_sha256": egress.get("access_context_sha256"),
        "extraction_schema_version": extraction_schema_version,
        "authorization_reference": egress.get("authorization_reference"),
        "audit_event_reference": egress.get("audit_event_reference"),
        "accounting": accounting,
        "field_provenance": provenance_refs,
        "field_failures": failures,
        "completed_at": completed_at,
        "secret_material_serialized": False,
        "model_execution_performed_by_this_module": False,
        "active_snapshot_promoted": False,
        "runtime_query_answered": False,
    }
    if _contains_secret_material(receipt):
        raise EgressPolicyError("model run receipt contains secret material")
    _write_json_once(receipt_path, receipt)
    return receipt
