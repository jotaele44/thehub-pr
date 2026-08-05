from __future__ import annotations

import copy
from pathlib import Path

import pytest

from evidence_engine._producer_admission_common import _inspect_package_files
from evidence_engine.producer_package_admission import (
    ProducerPackageAdmissionError,
    compute_producer_package_admission_decision,
    record_producer_package_admission,
)
from h07_support import (
    deterministic_lineage,
    job_record,
    job_spec,
    package_manifest,
    rebind_bundle,
    resign_lineage,
    run_receipt,
    valid_bundle,
    valid_model_field,
    valid_satim_signal,
    write_package,
)

SCHEMA_DIR = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "contracts"
    / "skywatcher_ai"
)


def _record(
    tmp_path: Path,
    admission_id: str,
    record,
    run,
    package,
    lineage,
    package_root: Path,
):
    return record_producer_package_admission(
        tmp_path / "storage",
        admission_id,
        record,
        run,
        package,
        lineage,
        package_root,
        completed_at="2026-07-31T01:10:00Z",
        schema_dir=SCHEMA_DIR,
    )


def _decision(record, run, package, lineage, package_root):
    report, _ = _inspect_package_files(
        package_root,
        package,
        record["job_spec"]["output_contract"]["write_root"],
    )
    return compute_producer_package_admission_decision(
        record,
        run,
        package,
        lineage,
        report,
    )


def test_valid_deterministic_package_is_admitted_to_quarantine(
    tmp_path: Path,
) -> None:
    record, run, package, lineage, package_root = valid_bundle(tmp_path)
    receipt = _record(
        tmp_path,
        "admission-1",
        record,
        run,
        package,
        lineage,
        package_root,
    )
    assert receipt["outcome"] == "ADMITTED"
    assert receipt["entry_accounting"] == {
        "expected": 2,
        "admitted": 2,
        "excluded": 0,
        "failed": 0,
        "complete": True,
    }
    assert receipt["source_accounting"]["complete"] is True
    assert receipt["acquisition_receipt_used"] is False
    assert receipt["active_snapshot_promoted"] is False
    quarantine = tmp_path / "storage" / "quarantine" / "sha256"
    assert len([path for path in quarantine.rglob("*") if path.is_file()]) == 2


def test_package_digest_mismatch_is_denied(tmp_path: Path) -> None:
    record, run, package, lineage, package_root = valid_bundle(tmp_path)
    package["package_sha256"] = "0" * 64
    run["package_sha256"] = package["package_sha256"]
    lineage["package_sha256"] = package["package_sha256"]
    resign_lineage(lineage)
    decision = _decision(record, run, package, lineage, package_root)
    assert decision["accepted"] is False
    assert "PACKAGE_IDENTITY_INVALID" in decision["reason_codes"]


def test_run_receipt_mismatch_is_denied(tmp_path: Path) -> None:
    record, run, package, lineage, package_root = valid_bundle(tmp_path)
    run["package_sha256"] = "0" * 64
    decision = _decision(record, run, package, lineage, package_root)
    assert decision["accepted"] is False
    assert "H06_RUN_RECEIPT_INVALID" in decision["reason_codes"]


def test_missing_output_lineage_is_denied(tmp_path: Path) -> None:
    record, run, package, lineage, package_root = valid_bundle(tmp_path)
    lineage["entries"].pop()
    resign_lineage(lineage)
    decision = _decision(record, run, package, lineage, package_root)
    assert decision["accepted"] is False
    assert {
        "OUTPUT_LINEAGE_PARTITION_INVALID",
        "MISSING_OUTPUT_LINEAGE",
    } <= set(decision["reason_codes"])


def test_unknown_source_artifact_is_denied(tmp_path: Path) -> None:
    record, run, package, lineage, package_root = valid_bundle(tmp_path)
    lineage["entries"][0]["source_artifact_ids"] = [
        "artifact-sha256-" + "9" * 64
    ]
    resign_lineage(lineage)
    decision = _decision(record, run, package, lineage, package_root)
    assert "UNKNOWN_SOURCE_ARTIFACT" in decision["reason_codes"]


def test_classification_downgrade_is_denied(tmp_path: Path) -> None:
    spec = job_spec()
    spec["input_artifacts"][0]["classification"].update(
        {
            "level": "RESTRICTED",
            "restriction_floor": "RESTRICTED",
        }
    )
    record = job_record(spec)
    package_root, entries = write_package(tmp_path)
    package = package_manifest(record, entries)
    run = run_receipt(record, package)
    lineage = deterministic_lineage(record, package)
    decision = _decision(record, run, package, lineage, package_root)
    assert {
        "OUTPUT_CLASSIFICATION_FLOOR_MISMATCH",
        "OUTPUT_CLASSIFICATION_DOWNGRADE",
    } <= set(decision["reason_codes"])


def test_test_only_is_propagated(tmp_path: Path) -> None:
    record, run, package, lineage, package_root = valid_bundle(
        tmp_path,
        test_only=True,
    )
    receipt = _record(
        tmp_path,
        "test-only-admission",
        record,
        run,
        package,
        lineage,
        package_root,
    )
    assert receipt["outcome"] == "ADMITTED"
    output_root = tmp_path / "storage" / "registry" / "producer_outputs"
    records = [
        path
        for path in output_root.rglob("*.json")
        if path.is_file()
    ]
    assert records
    assert all('"test_only":true' in path.read_text() for path in records)


def test_complete_model_field_provenance_is_accepted(
    tmp_path: Path,
) -> None:
    record, run, package, lineage, package_root = valid_bundle(tmp_path)
    entry = lineage["entries"][0]
    entry["derivation_kind"] = "MODEL_DERIVED"
    entry["model_field_provenance"] = [valid_model_field(record)]
    resign_lineage(lineage)
    receipt = _record(
        tmp_path,
        "model-admission",
        record,
        run,
        package,
        lineage,
        package_root,
    )
    assert receipt["outcome"] == "ADMITTED"


def test_missing_model_field_provenance_is_denied(
    tmp_path: Path,
) -> None:
    record, run, package, lineage, package_root = valid_bundle(tmp_path)
    lineage["entries"][0]["derivation_kind"] = "MODEL_DERIVED"
    resign_lineage(lineage)
    decision = _decision(record, run, package, lineage, package_root)
    assert "MODEL_FIELD_PROVENANCE_REQUIRED" in decision["reason_codes"]


def test_satim_provisional_true_is_accepted(tmp_path: Path) -> None:
    record, run, package, lineage, package_root = valid_bundle(tmp_path)
    entry = lineage["entries"][0]
    entry["derivation_kind"] = "SATIM_PROVISIONAL"
    entry["satim_signal"] = valid_satim_signal(record)
    resign_lineage(lineage)
    receipt = _record(
        tmp_path,
        "satim-admission",
        record,
        run,
        package,
        lineage,
        package_root,
    )
    assert receipt["outcome"] == "ADMITTED"
    assert receipt["citation_eligible"] is False


def test_satim_non_provisional_is_denied(tmp_path: Path) -> None:
    record, run, package, lineage, package_root = valid_bundle(tmp_path)
    entry = lineage["entries"][0]
    entry["derivation_kind"] = "SATIM_PROVISIONAL"
    signal = valid_satim_signal(record)
    signal["provisional"] = False
    entry["satim_signal"] = signal
    resign_lineage(lineage)
    decision = _decision(record, run, package, lineage, package_root)
    assert "SATIM_SIGNAL_NOT_PROVISIONAL" in decision["reason_codes"]


def test_output_path_escape_fails_closed(tmp_path: Path) -> None:
    record, run, package, lineage, package_root = valid_bundle(tmp_path)
    package["entries"][0]["relative_path"] = "../escape.json"
    rebind_bundle(record, run, package, lineage)
    with pytest.raises(
        ProducerPackageAdmissionError,
        match="package manifest violates",
    ):
        _record(
            tmp_path,
            "escape-admission",
            record,
            run,
            package,
            lineage,
            package_root,
        )


def test_symlink_is_denied(tmp_path: Path) -> None:
    record, run, package, lineage, package_root = valid_bundle(tmp_path)
    target = package_root / "target.txt"
    target.write_text("target")
    (package_root / "link.txt").symlink_to(target)
    decision = _decision(record, run, package, lineage, package_root)
    assert "PACKAGE_FILE_BOUNDARY_INVALID" in decision["reason_codes"]


def test_undeclared_file_is_denied(tmp_path: Path) -> None:
    record, run, package, lineage, package_root = valid_bundle(tmp_path)
    (package_root / "undeclared.log").write_text("unexpected")
    decision = _decision(record, run, package, lineage, package_root)
    assert "PACKAGE_FILE_BOUNDARY_INVALID" in decision["reason_codes"]


def test_output_digest_or_size_mismatch_is_denied(
    tmp_path: Path,
) -> None:
    record, run, package, lineage, package_root = valid_bundle(tmp_path)
    (package_root / "records.json").write_text('["changed"]\n')
    decision = _decision(record, run, package, lineage, package_root)
    assert "OUTPUT_DIGEST_OR_SIZE_MISMATCH" in decision["reason_codes"]


def test_admission_replay_is_idempotent(tmp_path: Path) -> None:
    record, run, package, lineage, package_root = valid_bundle(tmp_path)
    first = _record(
        tmp_path,
        "replay-admission",
        record,
        run,
        package,
        lineage,
        package_root,
    )
    replay = _record(
        tmp_path,
        "replay-admission",
        record,
        run,
        package,
        lineage,
        package_root,
    )
    assert replay == first


def test_changed_package_replay_conflicts(tmp_path: Path) -> None:
    record, run, package, lineage, package_root = valid_bundle(tmp_path)
    _record(
        tmp_path,
        "package-conflict",
        record,
        run,
        package,
        lineage,
        package_root,
    )
    changed_package = copy.deepcopy(package)
    changed_package["entries"][0]["size_bytes"] += 1
    with pytest.raises(
        ProducerPackageAdmissionError,
        match="changed job, run, package, or lineage",
    ):
        _record(
            tmp_path,
            "package-conflict",
            record,
            run,
            changed_package,
            lineage,
            package_root,
        )


def test_changed_lineage_replay_conflicts(tmp_path: Path) -> None:
    record, run, package, lineage, package_root = valid_bundle(tmp_path)
    _record(
        tmp_path,
        "lineage-conflict",
        record,
        run,
        package,
        lineage,
        package_root,
    )
    changed_lineage = copy.deepcopy(lineage)
    changed_lineage["entries"][0]["method_version"] = "2.0.0"
    resign_lineage(changed_lineage)
    with pytest.raises(
        ProducerPackageAdmissionError,
        match="changed job, run, package, or lineage",
    ):
        _record(
            tmp_path,
            "lineage-conflict",
            record,
            run,
            package,
            changed_lineage,
            package_root,
        )


def test_static_boundary_has_no_prohibited_runtime() -> None:
    module_root = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "evidence_engine"
    )
    source = "\n".join(
        (module_root / name).read_text(encoding="utf-8")
        for name in (
            "_producer_admission_common.py",
            "_producer_admission_metadata.py",
            "_producer_admission_identity.py",
            "_producer_admission_entries.py",
            "_producer_admission_accounting.py",
            "_producer_admission_lineage.py",
            "producer_package_admission.py",
        )
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
        "boto3",
        "google.generativeai",
        "import sqlalchemy",
        "import psycopg",
        "database_url",
        "launch_worker",
        "execute_model",
        "answer_query",
        "query_runtime",
        "retrieval_engine",
    )
    assert all(token not in source for token in forbidden)
