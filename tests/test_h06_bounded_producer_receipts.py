from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from control_plane import ProducerBoundaryError
from control_plane._producer_common import _job_identity
from h06_support import (
    _job, _package_digest, _record, _resign, _run_report, _write_outputs,
)

def test_output_path_escape_is_denied_and_accounted(tmp_path: Path) -> None:
    job = _job()
    output_root = tmp_path / "producer-output"
    output_root.mkdir()
    (tmp_path / "escape.json").write_bytes(b"escape\n")
    outputs = [
        {
            "output_id": "aviation_records",
            "relative_path": "../escape.json",
            "sha256": hashlib.sha256(b"escape\n").hexdigest(),
            "size_bytes": 7,
        }
    ]
    report = {
        "schema_version": "bounded_producer_run_report.v1",
        "job_spec_id": _job_identity(job)["job_spec_id"],
        "processed_inputs": [job["input_artifacts"][0]["artifact_id"]],
        "excluded_inputs": [],
        "failed_inputs": [],
        "outputs": outputs,
        "output_failures": [
            {"output_id": "provenance", "failure_code": "NOT_PRODUCED"}
        ],
        "duration_seconds": 1,
        "declared_package_sha256": _package_digest(job, []),
    }
    receipt = _record(tmp_path, "escape-run", job, report, output_root)
    assert receipt["outcome"] == "FAILED"
    assert "OUTPUT_PATH_ESCAPE_DENIED" in receipt["reason_codes"]


def test_undeclared_output_file_fails_closed(tmp_path: Path) -> None:
    job = _job()
    output_root = tmp_path / "producer-output"
    outputs = _write_outputs(output_root)
    (output_root / "undeclared.log").write_text("unexpected")
    report = _run_report(job, outputs)
    receipt = _record(tmp_path, "undeclared-run", job, report, output_root)
    assert receipt["outcome"] == "FAILED"
    assert "UNDECLARED_OUTPUT_FILE" in receipt["reason_codes"]


def test_resource_limit_violation_is_recorded(tmp_path: Path) -> None:
    job = _job()
    output_root = tmp_path / "producer-output"
    outputs = _write_outputs(output_root)
    report = _run_report(job, outputs)
    report["duration_seconds"] = 61
    receipt = _record(tmp_path, "limit-run", job, report, output_root)
    assert receipt["outcome"] == "FAILED"
    assert "RESOURCE_DURATION_LIMIT_EXCEEDED" in receipt["reason_codes"]
    assert receipt["resource_accounting"]["violations"]


def test_producer_package_digest_is_revalidated(tmp_path: Path) -> None:
    job = _job()
    output_root = tmp_path / "producer-output"
    outputs = _write_outputs(output_root)
    report = _run_report(job, outputs)
    report["declared_package_sha256"] = "0" * 64
    receipt = _record(tmp_path, "digest-run", job, report, output_root)
    assert receipt["outcome"] == "FAILED"
    assert "PRODUCER_PACKAGE_DIGEST_MISMATCH" in receipt["reason_codes"]
    manifest_path = (
        tmp_path
        / "storage"
        / "registry"
        / "producer_packages"
        / (receipt["package_sha256"] + ".json")
    )
    assert manifest_path.is_file()


def test_run_receipt_replay_is_idempotent(tmp_path: Path) -> None:
    job = _job()
    output_root = tmp_path / "producer-output"
    outputs = _write_outputs(output_root)
    report = _run_report(job, outputs)
    first = _record(tmp_path, "replay-run", job, report, output_root)
    replay = _record(tmp_path, "replay-run", job, report, output_root)
    assert replay == first
    assert first["outcome"] == "SUCCEEDED"


def test_changed_job_replay_conflicts(tmp_path: Path) -> None:
    job = _job()
    output_root = tmp_path / "producer-output"
    outputs = _write_outputs(output_root)
    report = _run_report(job, outputs)
    _record(tmp_path, "conflict-run", job, report, output_root)

    changed_job = copy.deepcopy(job)
    changed_job["operation_id"] = "aviation-extract-2"
    _resign(changed_job)
    changed_report = _run_report(changed_job, outputs)
    with pytest.raises(ProducerBoundaryError, match="different job, report, or package"):
        _record(
            tmp_path,
            "conflict-run",
            changed_job,
            changed_report,
            output_root,
        )


def test_incomplete_accounting_fails_closed_with_receipt(tmp_path: Path) -> None:
    job = _job()
    output_root = tmp_path / "producer-output"
    outputs = _write_outputs(output_root)
    report = _run_report(job, outputs)
    report["processed_inputs"] = []
    receipt = _record(tmp_path, "accounting-run", job, report, output_root)
    assert receipt["outcome"] == "FAILED"
    assert receipt["complete_accounting"] is False
    assert "COMPLETE_ACCOUNTING_REQUIRED" in receipt["reason_codes"]


def test_static_boundary_has_no_worker_or_provider_runtime() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "control_plane"
    source = (
        (root / "_producer_common.py").read_text()
        + (root / "_producer_job_identity.py").read_text()
        + (root / "_producer_job_policy.py").read_text()
        + (root / "producer_job.py").read_text()
        + (root / "_producer_output.py").read_text()
        + (root / "producer_run_receipt.py").read_text()
    ).lower()
    forbidden = (
        "import subprocess",
        "from subprocess",
        "docker",
        "kubernetes",
        "import requests",
        "from requests",
        "import httpx",
        "from httpx",
        "urllib.request",
        "anthropic",
        "openai",
        "boto3",
        "google.generativeai",
        "import sqlalchemy",
        "import psycopg",
        "database_url",
        "execute_model",
        "launch_worker",
        "answer_query",
        "query_runtime",
    )
    assert all(token not in source for token in forbidden)
