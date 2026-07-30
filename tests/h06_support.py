from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from control_plane import (
    ProducerBoundaryError,
    compute_bounded_producer_job_decision,
    record_bounded_producer_run,
)
from control_plane._producer_common import _canonical_bytes, _job_identity, _sha256

PRODUCER_REVISION = "1" * 40
PROFILE_SHA = "2" * 64
INPUT_SHA = "3" * 64


def _expected_pins() -> Dict[str, Any]:
    return {
        "producer_revision": PRODUCER_REVISION,
        "signed_command_policy_id": "signed-command-policy.v1",
        "worker_profile": {
            "profile_id": "skywatcher-bounded",
            "version": "worker-profile.v1",
            "sha256": PROFILE_SHA,
        },
        "schema_revisions": {
            "producer_package": "producer_package_manifest.v1",
            "aviation_extract": "aviation_extract.v1",
        },
    }


def _signature_value(payload: bytes) -> str:
    return hashlib.sha256(b"test-public-verifier:" + payload).hexdigest()


def _signature_verifier(
    signer_id: str, scheme: str, payload: bytes, signature: str
) -> bool:
    return (
        signer_id == "control-plane-test-signer"
        and scheme == "test-detached-sha256-v1"
        and signature == _signature_value(payload)
    )


def _authorization_verifier(
    authorization_reference: str, audit_reference: str, job_digest: str
) -> bool:
    return (
        authorization_reference == "authorization-h06-1"
        and audit_reference == "audit-h06-1"
        and len(job_digest) == 64
    )


def _resign(job: Dict[str, Any]) -> Dict[str, Any]:
    job.pop("signature", None)
    job.pop("job_id", None)
    identity_digest = _sha256(_canonical_bytes(job))
    job["job_id"] = "producer-job-sha256-" + identity_digest
    payload = _canonical_bytes(job)
    job["signature"] = {
        "scheme": "test-detached-sha256-v1",
        "signer_id": "control-plane-test-signer",
        "payload_sha256": _sha256(payload),
        "value": _signature_value(payload),
    }
    return job


def _job(*, snapshot_state: str = "ACTIVE") -> Dict[str, Any]:
    provisional = snapshot_state != "ACTIVE"
    job = {
        "schema_version": "bounded_producer_job.v2",
        "producer": "skywatcher-pr",
        "producer_revision": PRODUCER_REVISION,
        "operation_id": "aviation-extract-1",
        "signed_command_policy_id": "signed-command-policy.v1",
        "authorization_reference": "authorization-h06-1",
        "audit_event_reference": "audit-h06-1",
        "workflow_mode": (
            "PROVISIONAL_PROCESSING" if provisional else "ACTIVE_EVIDENCE"
        ),
        "capabilities": {
            "network_access": False,
            "model_operation": False,
        },
        "secret_references": ["secret://skywatcher-worker/runtime"],
        "input_artifacts": [
            {
                "artifact_id": "artifact-sha256-" + INPUT_SHA,
                "sha256": INPUT_SHA,
                "size_bytes": 6,
                "read_only_locator": "content://sha256/" + INPUT_SHA,
                "read_only": True,
                "snapshot_state": snapshot_state,
                "provisional": provisional,
                "classification": {
                    "level": "PUBLIC",
                    "restriction_floor": "PUBLIC",
                    "test_only": False,
                    "lineage_complete": True,
                },
            }
        ],
        "output_contract": {
            "schema_id": "skywatcher-producer-package",
            "schema_version": "producer_package_manifest.v1",
            "write_root": "producer-output",
            "required_outputs": ["aviation_records", "provenance"],
        },
        "pins": {
            "worker_profile": copy.deepcopy(_expected_pins()["worker_profile"]),
            "schema_revisions": copy.deepcopy(
                _expected_pins()["schema_revisions"]
            ),
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
        "created_at": "2026-07-30T22:00:00Z",
    }
    return _resign(job)


def _h05_receipt(job: Mapping[str, Any]) -> Dict[str, Any]:
    artifact = job["input_artifacts"][0]
    return {
        "schema_version": "egress_decision_receipt.v1",
        "decision_receipt_id": "egress-decision-sha256-" + "4" * 64,
        "allowed": True,
        "decision": "ALLOW_EXTERNAL",
        "authorization_reference": job["authorization_reference"],
        "audit_event_reference": job["audit_event_reference"],
        "artifact": {
            "artifact_id": artifact["artifact_id"],
            "sha256": artifact["sha256"],
            "snapshot_state": artifact["snapshot_state"],
        },
        "selected_provider": {
            "provider_id": "approved-network",
            "deployment": "EXTERNAL",
            "residency": "us-east",
            "model_id": "network-only",
            "model_revision": "rev-1",
            "credential_reference": "credential://network-only",
        },
        "policy_version": "egress-policy.v1",
        "access_context_sha256": "5" * 64,
    }


def _decision(job: Mapping[str, Any], receipt: Optional[Mapping[str, Any]] = None):
    return compute_bounded_producer_job_decision(
        job,
        _expected_pins(),
        signature_verifier=_signature_verifier,
        authorization_verifier=_authorization_verifier,
        h05_egress_receipt=receipt,
    )


def _write_outputs(root: Path) -> list[Dict[str, Any]]:
    root.mkdir()
    records = root / "records.json"
    provenance = root / "provenance.json"
    records.write_bytes(b"[]\n")
    provenance.write_bytes(b"{}\n")
    return [
        {
            "output_id": "aviation_records",
            "relative_path": "records.json",
            "sha256": hashlib.sha256(records.read_bytes()).hexdigest(),
            "size_bytes": records.stat().st_size,
        },
        {
            "output_id": "provenance",
            "relative_path": "provenance.json",
            "sha256": hashlib.sha256(provenance.read_bytes()).hexdigest(),
            "size_bytes": provenance.stat().st_size,
        },
    ]


def _package_digest(job: Mapping[str, Any], outputs: list[Dict[str, Any]]) -> str:
    decision = _decision(job)
    body = {
        "job_spec_id": decision["job_spec_id"],
        "job_spec_sha256": decision["signed_payload_sha256"],
        "producer": "skywatcher-pr",
        "producer_revision": decision["producer_revision"],
        "worker_profile": decision["pins"]["worker_profile"],
        "schema_revisions": decision["pins"]["schema_revisions"],
        "entries": sorted(
            outputs, key=lambda item: (item["output_id"], item["relative_path"])
        ),
    }
    return hashlib.sha256(_canonical_bytes(body)).hexdigest()


def _run_report(job: Mapping[str, Any], outputs: list[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "schema_version": "bounded_producer_run_report.v1",
        "job_spec_id": _job_identity(job)["job_spec_id"],
        "processed_inputs": [job["input_artifacts"][0]["artifact_id"]],
        "excluded_inputs": [],
        "failed_inputs": [],
        "outputs": outputs,
        "output_failures": [],
        "duration_seconds": 4.0,
        "declared_package_sha256": _package_digest(job, outputs),
    }


def _record(
    tmp_path: Path,
    run_id: str,
    job: Mapping[str, Any],
    report: Mapping[str, Any],
    output_root: Path,
    receipt: Optional[Mapping[str, Any]] = None,
):
    return record_bounded_producer_run(
        tmp_path / "storage",
        run_id,
        job,
        _expected_pins(),
        report,
        output_root,
        completed_at="2026-07-30T22:05:00Z",
        signature_verifier=_signature_verifier,
        authorization_verifier=_authorization_verifier,
        h05_egress_receipt=receipt,
    )
