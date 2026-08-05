from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple

from evidence_engine._producer_admission_common import (
    _job_identity,
    _lineage_identity,
    _package_identity,
    _sha256,
)

INPUT_SHA = "3" * 64
PRODUCER_REVISION = "1" * 40
PROFILE_SHA = "2" * 64


def job_spec(*, test_only: bool = False) -> Dict[str, Any]:
    classification = {
        "level": "TEST_ONLY" if test_only else "PUBLIC",
        "restriction_floor": "PUBLIC",
        "test_only": test_only,
        "lineage_complete": True,
    }
    spec = {
        "schema_version": "bounded_producer_job.v2",
        "producer": "skywatcher-pr",
        "producer_revision": PRODUCER_REVISION,
        "operation_id": "aviation-extract-1",
        "signed_command_policy_id": "signed-command-policy.v1",
        "authorization_reference": "authorization-h07-1",
        "audit_event_reference": "audit-h07-1",
        "workflow_mode": "ACTIVE_EVIDENCE",
        "capabilities": {
            "network_access": False,
            "model_operation": False,
        },
        "secret_references": ["secret://worker/runtime"],
        "input_artifacts": [
            {
                "artifact_id": "artifact-sha256-" + INPUT_SHA,
                "sha256": INPUT_SHA,
                "size_bytes": 6,
                "read_only_locator": "content://sha256/" + INPUT_SHA,
                "read_only": True,
                "snapshot_state": "ACTIVE",
                "provisional": False,
                "classification": classification,
            }
        ],
        "output_contract": {
            "schema_id": "skywatcher-producer-package",
            "schema_version": "producer_package_manifest.v1",
            "write_root": "producer-output",
            "required_outputs": ["aviation_records", "provenance"],
        },
        "pins": {
            "worker_profile": {
                "profile_id": "skywatcher-bounded",
                "version": "worker-profile.v1",
                "sha256": PROFILE_SHA,
            },
            "schema_revisions": {
                "aviation_extract": "aviation_extract.v1",
                "producer_package": "producer_package_manifest.v1",
            },
        },
        "workspace_policy": {
            "ephemeral": True,
            "persistent_db_mounts": False,
            "skywatcher_db_access": False,
            "thehub_db_access": False,
            "secret_readback": False,
            "unrestricted_shell": False,
            "database_mounts": [],
            "persistent_mounts": [],
        },
        "network_policy": {
            "default": "DENY",
            "approved_hosts": [],
            "max_requests": 0,
        },
        "resource_limits": {
            "max_duration_seconds": 60,
            "max_input_bytes": 1024,
            "max_output_bytes": 1024,
            "max_output_files": 4,
            "max_file_bytes": 512,
        },
        "requested_by": "operator-1",
        "created_at": "2026-07-31T01:00:00Z",
    }
    identity = _job_identity(spec)
    spec["job_id"] = identity["job_spec_id"]
    signed = _job_identity(spec)
    spec["signature"] = {
        "scheme": "test-detached-sha256-v1",
        "signer_id": "control-plane-test-signer",
        "payload_sha256": signed["signed_payload_sha256"],
        "value": "signature-value",
    }
    return spec


def job_record(spec: Mapping[str, Any]) -> Dict[str, Any]:
    identity = _job_identity(spec)
    return {
        "schema_version": "bounded_producer_job_record.v1",
        "job_spec_id": identity["job_spec_id"],
        "job_identity_sha256": identity["job_identity_sha256"],
        "signed_payload_sha256": identity["signed_payload_sha256"],
        "signature": {
            "verified": True,
            "signer_id": "control-plane-test-signer",
            "scheme": "test-detached-sha256-v1",
        },
        "authorization_verified": True,
        "egress_verified": False,
        "job_spec": copy.deepcopy(dict(spec)),
        "worker_execution_performed": False,
    }


def write_package(tmp_path: Path) -> Tuple[Path, list[Dict[str, Any]]]:
    package_root = tmp_path / "producer-output"
    package_root.mkdir()
    files = {
        "aviation_records": ("records.json", b"[]\n"),
        "provenance": ("provenance.json", b"{}\n"),
    }
    entries = []
    for output_id, (relative_path, data) in files.items():
        path = package_root / relative_path
        path.write_bytes(data)
        entries.append(
            {
                "output_id": output_id,
                "relative_path": relative_path,
                "sha256": _sha256(data),
                "size_bytes": len(data),
            }
        )
    entries.sort(key=lambda item: (item["output_id"], item["relative_path"]))
    return package_root, entries


def package_manifest(
    record: Mapping[str, Any],
    entries: list[Dict[str, Any]],
) -> Dict[str, Any]:
    spec = record["job_spec"]
    value = {
        "schema_version": "producer_package_manifest.v1",
        "job_spec_id": record["job_spec_id"],
        "job_spec_sha256": record["signed_payload_sha256"],
        "producer": "skywatcher-pr",
        "producer_revision": spec["producer_revision"],
        "worker_profile": copy.deepcopy(spec["pins"]["worker_profile"]),
        "schema_revisions": copy.deepcopy(spec["pins"]["schema_revisions"]),
        "entries": copy.deepcopy(entries),
        "active_snapshot_promoted": False,
        "query_serving_eligible": False,
    }
    identity = _package_identity(value)
    value.update(identity)
    return value


def run_receipt(
    record: Mapping[str, Any],
    package: Mapping[str, Any],
) -> Dict[str, Any]:
    expected = len(record["job_spec"]["input_artifacts"])
    required = len(package["entries"])
    return {
        "schema_version": "producer_run_receipt.v1",
        "producer_run_receipt_id": "producer-run-sha256-" + "4" * 64,
        "run_id": "run-h07-1",
        "job_spec_id": record["job_spec_id"],
        "job_spec_sha256": record["signed_payload_sha256"],
        "run_report_sha256": "5" * 64,
        "producer_package_id": package["producer_package_id"],
        "package_sha256": package["package_sha256"],
        "outcome": "SUCCEEDED",
        "reason_codes": [],
        "authorization_reference": "authorization-h07-1",
        "audit_event_reference": "audit-h07-1",
        "signature": {
            "verified": True,
            "signer_id": "control-plane-test-signer",
            "scheme": "test-detached-sha256-v1",
        },
        "h05_egress_verified": False,
        "input_accounting": {
            "expected": expected,
            "processed": expected,
            "excluded": 0,
            "failed": 0,
            "complete": True,
            "processed_inputs": [
                record["job_spec"]["input_artifacts"][0]["artifact_id"]
            ],
            "excluded_inputs": [],
            "failed_inputs": [],
        },
        "output_accounting": {
            "required": required,
            "declared_outputs": required,
            "verified_outputs": required,
            "declared_failures": 0,
            "verification_failures": [],
            "complete": True,
        },
        "output_failures": [],
        "resource_accounting": {},
        "complete_accounting": True,
        "completed_at": "2026-07-31T01:05:00Z",
        "secret_material_serialized": False,
        "worker_execution_performed_by_this_module": False,
        "provider_execution_performed": False,
        "model_execution_performed": False,
        "active_snapshot_promoted": False,
        "runtime_query_answered": False,
    }


def deterministic_lineage(
    record: Mapping[str, Any],
    package: Mapping[str, Any],
    *,
    test_only: bool = False,
) -> Dict[str, Any]:
    source = record["job_spec"]["input_artifacts"][0]
    classification = {
        "level": "TEST_ONLY" if test_only else "PUBLIC",
        "restriction_floor": "PUBLIC",
        "test_only": test_only,
        "lineage_complete": True,
    }
    entries = [
        {
            "output_id": item["output_id"],
            "output_sha256": item["sha256"],
            "source_artifact_ids": [source["artifact_id"]],
            "classification": copy.deepcopy(classification),
            "derivation_kind": "DETERMINISTIC",
            "method": "aviation-normalization",
            "method_version": "1.0.0",
            "output_schema_id": item["output_id"],
            "output_schema_version": "1.0.0",
        }
        for item in package["entries"]
    ]
    value = {
        "schema_version": "producer_output_lineage.v1",
        "producer_package_id": package["producer_package_id"],
        "package_sha256": package["package_sha256"],
        "job_spec_id": record["job_spec_id"],
        "entries": entries,
        "source_dispositions": [
            {
                "artifact_id": source["artifact_id"],
                "disposition": "USED",
            }
        ],
        "created_at": "2026-07-31T01:06:00Z",
    }
    value["lineage_manifest_id"] = _lineage_identity(value)[
        "lineage_manifest_id"
    ]
    return value


def resign_lineage(lineage: Dict[str, Any]) -> None:
    lineage.pop("lineage_manifest_id", None)
    lineage["lineage_manifest_id"] = _lineage_identity(lineage)[
        "lineage_manifest_id"
    ]


def valid_bundle(
    tmp_path: Path,
    *,
    test_only: bool = False,
):
    spec = job_spec(test_only=test_only)
    record = job_record(spec)
    package_root, entries = write_package(tmp_path)
    package = package_manifest(record, entries)
    run = run_receipt(record, package)
    lineage = deterministic_lineage(
        record,
        package,
        test_only=test_only,
    )
    return record, run, package, lineage, package_root


def rebind_bundle(
    record: Mapping[str, Any],
    run: Dict[str, Any],
    package: Dict[str, Any],
    lineage: Dict[str, Any],
) -> None:
    package.pop("producer_package_id", None)
    package.pop("package_sha256", None)
    package["job_spec_id"] = record["job_spec_id"]
    package["job_spec_sha256"] = record["signed_payload_sha256"]
    identity = _package_identity(package)
    package.update(identity)
    run["job_spec_id"] = record["job_spec_id"]
    run["job_spec_sha256"] = record["signed_payload_sha256"]
    run["producer_package_id"] = package["producer_package_id"]
    run["package_sha256"] = package["package_sha256"]
    lineage["producer_package_id"] = package["producer_package_id"]
    lineage["package_sha256"] = package["package_sha256"]
    lineage["job_spec_id"] = record["job_spec_id"]
    resign_lineage(lineage)


def valid_model_field(
    record: Mapping[str, Any],
    *,
    field_id: str = "field-1",
) -> Dict[str, Any]:
    source = record["job_spec"]["input_artifacts"][0]
    return {
        "schema_version": "model_field_provenance.v1",
        "field_id": field_id,
        "source_artifact_id": source["artifact_id"],
        "source_sha256": source["sha256"],
        "source_region": None,
        "model_run_receipt_id": "model-run-1",
        "provider": "approved-provider",
        "model": "vision-model",
        "model_revision": "revision-1",
        "prompt_template_version": "prompt-v1",
        "prompt_hash": "6" * 64,
        "policy_version": "egress-policy.v1",
        "access_context_hash": "7" * 64,
        "extraction_schema_version": "aviation_extract.v1",
        "field_name": "registration",
        "value": "N12345",
        "confidence": 0.9,
        "validation_outcome": "VALID",
        "review_status": "UNREVIEWED",
        "reviewer_id": None,
        "created_at": "2026-07-31T01:07:00Z",
        "supersedes_field_id": None,
    }


def valid_satim_signal(record: Mapping[str, Any]) -> Dict[str, Any]:
    source = record["job_spec"]["input_artifacts"][0]
    return {
        "schema_version": "satim_provisional_signal.v1",
        "signal_id": "signal-1",
        "source_artifact_ids": [source["artifact_id"]],
        "method": "PIXEL_DIFFERENCE",
        "method_version": "1.0.0",
        "parameters": {},
        "result": {"changed_fraction": 0.1},
        "confidence": 0.7,
        "provisional": True,
        "review_status": "NEEDS_REVIEW",
        "created_at": "2026-07-31T01:07:00Z",
    }
