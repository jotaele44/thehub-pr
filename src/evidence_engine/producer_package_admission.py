"""Offline H07 producer-package quarantine and immutable admission records."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from ._producer_admission_common import (
    ProducerPackageAdmissionError,
    _admission_receipt_path,
    _contains_secret_material,
    _detect_mime_type,
    _inspect_package_files,
    _mapping,
    _record_digests,
    _replay_existing_receipt,
    _safe_write_once,
    _sha256,
    _write_json_once,
    validate_producer_package_records,
)
from ._producer_admission_lineage import (
    compute_producer_package_admission_decision,
)

def record_producer_package_admission(
    storage_root: Path,
    admission_id: str,
    job_record: Mapping[str, Any],
    run_receipt: Mapping[str, Any],
    package_manifest: Mapping[str, Any],
    lineage_manifest: Mapping[str, Any],
    package_root: Path,
    *,
    completed_at: str,
    schema_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Validate and immutably quarantine one supplied producer package."""
    normalized_admission_id = admission_id.strip()
    if not normalized_admission_id:
        raise ProducerPackageAdmissionError("admission_id is required")
    digests = _record_digests(
        job_record,
        run_receipt,
        package_manifest,
        lineage_manifest,
    )
    receipt_path = _admission_receipt_path(
        Path(storage_root),
        normalized_admission_id,
    )
    replay = _replay_existing_receipt(receipt_path, digests)
    if replay is not None:
        return replay

    validate_producer_package_records(
        job_record,
        run_receipt,
        package_manifest,
        lineage_manifest,
        schema_dir=schema_dir,
    )
    job_spec = _mapping(job_record.get("job_spec"))
    expected_write_root = str(
        _mapping(job_spec.get("output_contract")).get("write_root") or ""
    )
    file_report, verified_paths = _inspect_package_files(
        Path(package_root),
        package_manifest,
        expected_write_root,
    )
    decision = compute_producer_package_admission_decision(
        job_record,
        run_receipt,
        package_manifest,
        lineage_manifest,
        file_report,
    )

    root = Path(storage_root)
    lineage_map = {
        str(item.get("output_id") or ""): dict(item)
        for item in lineage_manifest.get("entries", [])
        if isinstance(item, Mapping)
    }
    package_map = {
        str(item.get("output_id") or ""): dict(item)
        for item in package_manifest.get("entries", [])
        if isinstance(item, Mapping)
    }
    output_records: List[Dict[str, Any]] = []
    provenance_records: List[Dict[str, Any]] = []

    if decision["accepted"]:
        cached_bytes: Dict[str, bytes] = {}
        for output_id in sorted(package_map):
            path = verified_paths.get(output_id)
            if path is None:
                raise ProducerPackageAdmissionError(
                    "accepted package is missing a verified output path"
                )
            data = path.read_bytes()
            digest = str(package_map[output_id]["sha256"])
            if _sha256(data) != digest:
                raise ProducerPackageAdmissionError(
                    "package output changed after admission verification"
                )
            cached_bytes[output_id] = data
            quarantine_path = (
                root
                / "quarantine"
                / "sha256"
                / digest[:2]
                / digest
            )
            _safe_write_once(quarantine_path, data)

        for output_id in sorted(package_map):
            entry = package_map[output_id]
            lineage = lineage_map[output_id]
            data = cached_bytes[output_id]
            digest = str(entry["sha256"])
            quarantine_path = (
                root
                / "quarantine"
                / "sha256"
                / digest[:2]
                / digest
            )
            record_key = _sha256(
                (
                    str(package_manifest["producer_package_id"])
                    + ":"
                    + output_id
                ).encode("utf-8")
            )
            output_record = {
                "schema_version": "producer_output_content.v1",
                "producer_output_record_id": (
                    "producer-output-sha256-" + record_key
                ),
                "artifact_id": "artifact-sha256-" + digest,
                "sha256": digest,
                "size_bytes": len(data),
                "mime_type": _detect_mime_type(data),
                "quarantine_locator": quarantine_path.relative_to(
                    root
                ).as_posix(),
                "lifecycle_state": "QUARANTINED",
                "source_kind": "SKYWATCHER_PRODUCER_OUTPUT",
                "producer_package_id": package_manifest[
                    "producer_package_id"
                ],
                "producer_run_receipt_id": run_receipt[
                    "producer_run_receipt_id"
                ],
                "job_spec_id": job_record["job_spec_id"],
                "output_id": output_id,
                "classification": lineage["classification"],
                "classification_lineage_complete": True,
                "active_snapshot_eligible": False,
                "answer_eligible": False,
                "claim_eligible": False,
                "retrieval_eligible": False,
                "citation_eligible": False,
            }
            provenance_key = _sha256(
                (
                    str(lineage_manifest["lineage_manifest_id"])
                    + ":"
                    + output_id
                ).encode("utf-8")
            )
            provenance_record = {
                "schema_version": "producer_output_provenance_edge.v1",
                "provenance_edge_id": (
                    "producer-provenance-sha256-" + provenance_key
                ),
                "producer_output_record_id": output_record[
                    "producer_output_record_id"
                ],
                "output_artifact_id": output_record["artifact_id"],
                "output_sha256": digest,
                "source_artifact_ids": lineage[
                    "source_artifact_ids"
                ],
                "producer_package_id": package_manifest[
                    "producer_package_id"
                ],
                "producer_run_receipt_id": run_receipt[
                    "producer_run_receipt_id"
                ],
                "lineage_manifest_id": lineage_manifest[
                    "lineage_manifest_id"
                ],
                "derivation_kind": lineage["derivation_kind"],
                "method": lineage["method"],
                "method_version": lineage["method_version"],
                "output_schema_id": lineage["output_schema_id"],
                "output_schema_version": lineage[
                    "output_schema_version"
                ],
                "model_field_provenance": lineage.get(
                    "model_field_provenance",
                    [],
                ),
                "satim_signal": lineage.get("satim_signal"),
                "review_and_certification_distinct": True,
                "certified_state_created": False,
                "active_snapshot_promoted": False,
            }
            output_path = (
                root
                / "registry"
                / "producer_outputs"
                / record_key[:2]
                / (record_key + ".json")
            )
            provenance_path = (
                root
                / "registry"
                / "provenance"
                / "producer_outputs"
                / (provenance_key + ".json")
            )
            _write_json_once(output_path, output_record)
            _write_json_once(provenance_path, provenance_record)
            output_records.append(output_record)
            provenance_records.append(provenance_record)

    dispositions: List[Dict[str, Any]] = []
    for item in decision["dispositions"]:
        value = dict(item)
        if decision["accepted"]:
            value["disposition"] = "ADMITTED"
        dispositions.append(value)
    receipt = {
        "schema_version": "producer_package_admission_receipt.v1",
        "admission_receipt_id": (
            "producer-admission-sha256-"
            + _sha256(normalized_admission_id.encode("utf-8"))
        ),
        "admission_id": normalized_admission_id,
        **digests,
        "package_sha256": package_manifest.get("package_sha256"),
        "outcome": "ADMITTED" if decision["accepted"] else "DENIED",
        "reason_codes": decision["reason_codes"],
        "authorization_reference": decision[
            "authorization_reference"
        ],
        "audit_event_reference": decision["audit_event_reference"],
        "entry_accounting": decision["entry_accounting"],
        "source_accounting": decision["source_accounting"],
        "dispositions": dispositions,
        "output_record_ids": [
            item["producer_output_record_id"] for item in output_records
        ],
        "provenance_edge_ids": [
            item["provenance_edge_id"] for item in provenance_records
        ],
        "completed_at": completed_at,
        "quarantine_before_registry": True,
        "acquisition_receipt_used": False,
        "certified_state_created": False,
        "active_snapshot_promoted": False,
        "answer_eligible": False,
        "claim_eligible": False,
        "retrieval_eligible": False,
        "citation_eligible": False,
    }
    if _contains_secret_material(receipt):
        raise ProducerPackageAdmissionError(
            "producer admission receipt contains secret material"
        )
    try:
        _write_json_once(receipt_path, receipt)
    except Exception as exc:
        raise ProducerPackageAdmissionError(
            "immutable producer admission receipt write failed"
        ) from exc
    return receipt

__all__ = [
    "ProducerPackageAdmissionError",
    "compute_producer_package_admission_decision",
    "record_producer_package_admission",
    "validate_producer_package_records",
]
