"""H07 H06-record identity and package/lineage binding checks."""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from ._producer_admission_common import (
    _contains_secret_material,
    _job_identity,
    _lineage_identity,
    _mapping,
    _package_identity,
)


def _validate_identity_bindings(
    job_record: Mapping[str, Any],
    run_receipt: Mapping[str, Any],
    package_manifest: Mapping[str, Any],
    lineage_manifest: Mapping[str, Any],
) -> Dict[str, Any]:
    job = _mapping(job_record)
    run = _mapping(run_receipt)
    package = _mapping(package_manifest)
    lineage = _mapping(lineage_manifest)
    reasons: List[str] = []
    if any(_contains_secret_material(value) for value in (job, run, package, lineage)):
        reasons.append("SECRET_MATERIAL_PRESENT")

    job_spec = _mapping(job.get("job_spec"))
    identity = _job_identity(job_spec)
    if (
        job.get("schema_version") != "bounded_producer_job_record.v1"
        or job.get("job_spec_id") != identity["job_spec_id"]
        or job.get("job_identity_sha256") != identity["job_identity_sha256"]
        or job.get("signed_payload_sha256") != identity["signed_payload_sha256"]
        or _mapping(job.get("signature")).get("verified") is not True
        or job.get("authorization_verified") is not True
        or job.get("worker_execution_performed") is not False
    ):
        reasons.append("H06_JOB_RECORD_IDENTITY_INVALID")

    package_identity = _package_identity(package)
    if (
        package.get("schema_version") != "producer_package_manifest.v1"
        or package.get("producer_package_id") != package_identity["producer_package_id"]
        or package.get("package_sha256") != package_identity["package_sha256"]
        or package.get("active_snapshot_promoted") is not False
        or package.get("query_serving_eligible") is not False
    ):
        reasons.append("PACKAGE_IDENTITY_INVALID")

    if (
        run.get("schema_version") != "producer_run_receipt.v1"
        or run.get("job_spec_id") != job.get("job_spec_id")
        or run.get("job_spec_sha256") != job.get("signed_payload_sha256")
        or run.get("producer_package_id") != package.get("producer_package_id")
        or run.get("package_sha256") != package.get("package_sha256")
        or run.get("outcome") != "SUCCEEDED"
        or run.get("reason_codes") not in ([], None)
        or run.get("complete_accounting") is not True
        or _mapping(run.get("input_accounting")).get("complete") is not True
        or _mapping(run.get("output_accounting")).get("complete") is not True
        or run.get("output_failures") not in ([], None)
        or run.get("secret_material_serialized") is not False
        or run.get("worker_execution_performed_by_this_module") is not False
        or run.get("provider_execution_performed") is not False
        or run.get("model_execution_performed") is not False
        or run.get("active_snapshot_promoted") is not False
        or run.get("runtime_query_answered") is not False
    ):
        reasons.append("H06_RUN_RECEIPT_INVALID")

    job_inputs = [dict(item) for item in job_spec.get("input_artifacts", []) if isinstance(item, Mapping)]
    source_map = {str(item.get("artifact_id") or ""): item for item in job_inputs}
    required_outputs = set(
        str(item)
        for item in _mapping(job_spec.get("output_contract")).get("required_outputs", [])
    )
    package_entries = [dict(item) for item in package.get("entries", []) if isinstance(item, Mapping)]
    package_map = {str(item.get("output_id") or ""): item for item in package_entries}
    if len(package_map) != len(package_entries) or set(package_map) != required_outputs:
        reasons.append("PACKAGE_OUTPUT_PARTITION_INVALID")
    if (
        package.get("job_spec_id") != job.get("job_spec_id")
        or package.get("job_spec_sha256") != job.get("signed_payload_sha256")
        or package.get("producer_revision") != job_spec.get("producer_revision")
        or package.get("worker_profile") != _mapping(job_spec.get("pins")).get("worker_profile")
        or package.get("schema_revisions") != _mapping(job_spec.get("pins")).get("schema_revisions")
    ):
        reasons.append("PACKAGE_JOB_BINDING_INVALID")

    lineage_identity = _lineage_identity(lineage)
    if (
        lineage.get("schema_version") != "producer_output_lineage.v1"
        or lineage.get("lineage_manifest_id") != lineage_identity["lineage_manifest_id"]
        or lineage.get("producer_package_id") != package.get("producer_package_id")
        or lineage.get("package_sha256") != package.get("package_sha256")
        or lineage.get("job_spec_id") != job.get("job_spec_id")
    ):
        reasons.append("LINEAGE_MANIFEST_IDENTITY_INVALID")

    lineage_entries = [dict(item) for item in lineage.get("entries", []) if isinstance(item, Mapping)]
    lineage_map = {str(item.get("output_id") or ""): item for item in lineage_entries}
    if len(lineage_map) != len(lineage_entries) or set(lineage_map) != set(package_map):
        reasons.append("OUTPUT_LINEAGE_PARTITION_INVALID")
    return {
        "job": job,
        "run": run,
        "package": package,
        "lineage": lineage,
        "job_spec": job_spec,
        "source_map": source_map,
        "package_map": package_map,
        "lineage_map": lineage_map,
        "reasons": reasons,
    }


__all__ = ["_validate_identity_bindings"]
