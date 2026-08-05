"""Immutable H06 producer package and run receipts; no worker execution."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from ._producer_common import (
    ProducerBoundaryError, _canonical_bytes, _contains_secret_material, _load_json, _mapping,
    _sha256, _write_json_once,
)
from ._producer_output import (
    _account_inputs, _output_partition, _package_manifest, _resource_accounting,
    _verify_outputs,
)
from .producer_job import (
    AuthorizationVerifier, SignatureVerifier, compute_bounded_producer_job_decision,
)

def record_bounded_producer_run(
    storage_root: Path,
    run_id: str,
    job_spec: Mapping[str, Any],
    expected_pins: Mapping[str, Any],
    run_report: Mapping[str, Any],
    output_root: Path,
    *,
    completed_at: str,
    signature_verifier: SignatureVerifier,
    authorization_verifier: AuthorizationVerifier,
    h05_egress_receipt: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate supplied worker results and persist immutable H06 records."""
    normalized_run_id = run_id.strip()
    if not normalized_run_id:
        raise ProducerBoundaryError("run_id is required")
    report = dict(run_report) if isinstance(run_report, Mapping) else {}
    if _contains_secret_material(report):
        raise ProducerBoundaryError("run report contains secret material")

    decision = compute_bounded_producer_job_decision(
        job_spec,
        expected_pins,
        signature_verifier=signature_verifier,
        authorization_verifier=authorization_verifier,
        h05_egress_receipt=h05_egress_receipt,
    )
    if decision.get("accepted") is not True:
        raise ProducerBoundaryError(
            "bounded producer job denied: " + ",".join(decision.get("reason_codes", []))
        )
    if report.get("schema_version") != "bounded_producer_run_report.v1":
        raise ProducerBoundaryError("run report schema is invalid")
    if report.get("job_spec_id") != decision.get("job_spec_id"):
        raise ProducerBoundaryError("run report job identity mismatch")

    reasons: List[str] = []
    expected_input_ids = {
        str(item["artifact_id"])
        for item in _mapping(decision.get("inputs")).get("artifacts", [])
    }
    input_accounting = _account_inputs(expected_input_ids, report, reasons)
    required_output_ids = set(
        _mapping(decision.get("output_contract")).get("required_outputs", [])
    )
    outputs, declared_output_failures, output_complete = _output_partition(
        required_output_ids, report, reasons
    )
    (
        verified_outputs,
        verification_failures,
        observed_output_bytes,
        observed_output_files,
    ) = _verify_outputs(
        Path(output_root),
        str(_mapping(decision.get("output_contract")).get("write_root") or ""),
        outputs,
        _mapping(decision.get("resource_limits")),
        reasons,
    )
    resources = _resource_accounting(
        decision,
        report,
        observed_output_bytes,
        observed_output_files,
        reasons,
    )
    manifest = _package_manifest(decision, verified_outputs)
    if report.get("declared_package_sha256") != manifest["package_sha256"]:
        reasons.append("PRODUCER_PACKAGE_DIGEST_MISMATCH")

    reasons = sorted(set(reasons))
    accounting_complete = input_accounting["complete"] and output_complete
    if not accounting_complete:
        reasons = sorted(set(reasons + ["COMPLETE_ACCOUNTING_REQUIRED"]))
    all_output_failures = sorted(
        declared_output_failures + verification_failures,
        key=lambda item: (str(item.get("output_id")), str(item.get("failure_code"))),
    )
    if reasons:
        outcome = "FAILED"
    elif all_output_failures or input_accounting["excluded"]:
        outcome = "PARTIAL"
    else:
        outcome = "SUCCEEDED"

    root = Path(storage_root)
    run_key = _sha256(normalized_run_id.encode("utf-8"))
    report_digest = _sha256(_canonical_bytes(report))
    receipt_path = root / "registry" / "producer_runs" / (run_key + ".json")
    if receipt_path.exists():
        try:
            existing = _load_json(receipt_path, "producer run receipt")
        except Exception as exc:
            raise ProducerBoundaryError(
                "existing producer run receipt is invalid"
            ) from exc
        if (
            existing.get("job_spec_sha256") != decision["signed_payload_sha256"]
            or existing.get("run_report_sha256") != report_digest
            or existing.get("package_sha256") != manifest["package_sha256"]
        ):
            raise ProducerBoundaryError(
                "run_id already exists with different job, report, or package"
            )
        return existing

    job_record = {
        "schema_version": "bounded_producer_job_record.v1",
        "job_spec_id": decision["job_spec_id"],
        "job_identity_sha256": decision["job_identity_sha256"],
        "signed_payload_sha256": decision["signed_payload_sha256"],
        "signature": decision["signature"],
        "authorization_verified": decision["authorization_verified"],
        "egress_verified": decision["egress_verified"],
        "job_spec": dict(job_spec),
        "worker_execution_performed": False,
    }
    if _contains_secret_material(job_record):
        raise ProducerBoundaryError("job record contains secret material")
    job_path = (
        root
        / "registry"
        / "producer_job_specs"
        / (decision["job_identity_sha256"] + ".json")
    )
    package_path = (
        root
        / "registry"
        / "producer_packages"
        / (manifest["package_sha256"] + ".json")
    )
    try:
        _write_json_once(job_path, job_record)
        _write_json_once(package_path, manifest)
    except Exception as exc:
        raise ProducerBoundaryError(
            "immutable job or package record write failed"
        ) from exc

    receipt = {
        "schema_version": "producer_run_receipt.v1",
        "producer_run_receipt_id": "producer-run-sha256-" + run_key,
        "run_id": normalized_run_id,
        "job_spec_id": decision["job_spec_id"],
        "job_spec_sha256": decision["signed_payload_sha256"],
        "run_report_sha256": report_digest,
        "producer_package_id": manifest["producer_package_id"],
        "package_sha256": manifest["package_sha256"],
        "outcome": outcome,
        "reason_codes": reasons,
        "authorization_reference": decision["authorization_reference"],
        "audit_event_reference": decision["audit_event_reference"],
        "signature": decision["signature"],
        "h05_egress_verified": decision["egress_verified"],
        "input_accounting": input_accounting,
        "output_accounting": {
            "required": len(required_output_ids),
            "declared_outputs": len(outputs),
            "verified_outputs": len(verified_outputs),
            "declared_failures": len(declared_output_failures),
            "verification_failures": verification_failures,
            "complete": output_complete,
        },
        "output_failures": all_output_failures,
        "resource_accounting": resources,
        "complete_accounting": accounting_complete,
        "completed_at": completed_at,
        "secret_material_serialized": False,
        "worker_execution_performed_by_this_module": False,
        "provider_execution_performed": False,
        "model_execution_performed": False,
        "active_snapshot_promoted": False,
        "runtime_query_answered": False,
    }
    if _contains_secret_material(receipt):
        raise ProducerBoundaryError("producer run receipt contains secret material")
    try:
        _write_json_once(receipt_path, receipt)
    except Exception as exc:
        raise ProducerBoundaryError(
            "immutable producer run receipt write failed"
        ) from exc
    return receipt

__all__ = ["record_bounded_producer_run"]
