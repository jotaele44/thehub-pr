"""Pure H04 certification gates and immutable candidate construction.

H04 consumes only H03 validation reports and their locally referenced immutable
artifacts. It does not promote an ACTIVE snapshot or answer user queries.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple


class SnapshotCertificationError(RuntimeError):
    """Raised when a certification candidate cannot be handled safely."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _artifact_id(digest: str) -> str:
    return "artifact-sha256-" + digest


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _safe_write_once(path: Path, data: bytes) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise SnapshotCertificationError(
                "immutable path content conflict: " + str(path)
            )
        return False
    fd, temporary_name = tempfile.mkstemp(
        prefix=".certify-", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(str(temporary), str(path))
            return True
        except FileExistsError:
            if path.read_bytes() != data:
                raise SnapshotCertificationError(
                    "immutable path content conflict: " + str(path)
                )
            return False
    finally:
        temporary.unlink(missing_ok=True)


def _write_json_once(path: Path, value: Mapping[str, Any]) -> bool:
    return _safe_write_once(path, _canonical_bytes(dict(value)) + b"\n")


def _load_json(path: Path, label: str) -> Dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise SnapshotCertificationError(label + " must be a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SnapshotCertificationError(
            label + " is not valid UTF-8 JSON"
        ) from exc
    if not isinstance(value, dict):
        raise SnapshotCertificationError(label + " must contain a JSON object")
    return value


def _resolve_local_locator(root: Path, locator: Any, label: str) -> Path:
    if not isinstance(locator, str) or not locator:
        raise SnapshotCertificationError(label + " locator is required")
    relative = Path(locator)
    if relative.is_absolute() or ".." in relative.parts:
        raise SnapshotCertificationError(label + " locator escapes storage root")
    root_resolved = root.resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise SnapshotCertificationError(
            label + " locator escapes storage root"
        ) from exc
    return candidate


def _verify_validated_disposition(
    root: Path, row: Mapping[str, Any]
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    failures: List[str] = []
    derivative_sha = str(row.get("derivative_sha256") or "")
    derivative_id = str(row.get("derivative_artifact_id") or "")
    source_sha = str(row.get("source_sha256") or "")
    source_id = str(row.get("source_artifact_id") or "")
    if (
        len(derivative_sha) != 64
        or any(ch not in "0123456789abcdef" for ch in derivative_sha)
        or derivative_id != _artifact_id(derivative_sha)
    ):
        failures.append("DERIVATIVE_IDENTITY_INVALID")
    if (
        len(source_sha) != 64
        or any(ch not in "0123456789abcdef" for ch in source_sha)
        or source_id != _artifact_id(source_sha)
    ):
        failures.append("SOURCE_IDENTITY_INVALID")
    if failures:
        return None, failures

    try:
        derivative_path = _resolve_local_locator(
            root, row.get("derivative_locator"), "derivative"
        )
        derivative_record_path = _resolve_local_locator(
            root,
            row.get("derivative_content_record_locator"),
            "derivative content record",
        )
        provenance_path = _resolve_local_locator(
            root, row.get("provenance_locator"), "provenance"
        )
    except SnapshotCertificationError:
        return None, ["LOCATOR_INVALID"]

    if not derivative_path.is_file() or derivative_path.is_symlink():
        return None, ["DERIVATIVE_BYTES_UNAVAILABLE"]
    derivative_bytes = derivative_path.read_bytes()
    if _sha256(derivative_bytes) != derivative_sha:
        failures.append("DERIVATIVE_DIGEST_MISMATCH")

    try:
        derivative_record = _load_json(
            derivative_record_path, "derivative content record"
        )
    except SnapshotCertificationError:
        derivative_record = {}
        failures.append("DERIVATIVE_RECORD_UNAVAILABLE")
    if derivative_record and (
        derivative_record.get("schema_version")
        != "normalized_derivative_content.v1"
        or derivative_record.get("derivative_artifact_id") != derivative_id
        or derivative_record.get("derivative_sha256") != derivative_sha
        or derivative_record.get("lifecycle_state") != "QUARANTINED"
        or derivative_record.get("active_snapshot_eligible") is not False
    ):
        failures.append("DERIVATIVE_RECORD_INVALID")

    try:
        provenance = _load_json(provenance_path, "provenance edge")
    except SnapshotCertificationError:
        provenance = {}
        failures.append("PROVENANCE_UNAVAILABLE")
    if provenance and (
        provenance.get("schema_version")
        != "source_derivative_provenance_edge.v1"
        or provenance.get("source_artifact_id") != source_id
        or provenance.get("source_sha256") != source_sha
        or provenance.get("derivative_artifact_id") != derivative_id
        or provenance.get("derivative_sha256") != derivative_sha
        or provenance.get("lifecycle_state") != "QUARANTINED"
        or provenance.get("active_snapshot_eligible") is not False
    ):
        failures.append("PROVENANCE_INVALID")

    classification = provenance.get("classification")
    if not isinstance(classification, Mapping):
        failures.append("CLASSIFICATION_LINEAGE_UNAVAILABLE")
        classification = {}
    elif classification.get("lineage_complete") is not True:
        failures.append("CLASSIFICATION_LINEAGE_INCOMPLETE")
    if failures:
        return None, sorted(set(failures))

    return {
        "source_artifact_id": source_id,
        "source_sha256": source_sha,
        "derivative_artifact_id": derivative_id,
        "derivative_sha256": derivative_sha,
        "derivative_locator": str(row["derivative_locator"]),
        "derivative_content_record_locator": str(
            row["derivative_content_record_locator"]
        ),
        "provenance_locator": str(row["provenance_locator"]),
        "provenance_edge_id": str(provenance.get("provenance_edge_id") or ""),
        "normalization": provenance.get("normalization"),
        "classification": dict(classification),
        "derivative_size_bytes": len(derivative_bytes),
        "derivative_record_sha256": _sha256(_canonical_bytes(derivative_record)),
        "provenance_sha256": _sha256(_canonical_bytes(provenance)),
    }, []


def compute_snapshot_gate(candidate_manifest: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a pure, deterministic certification decision."""
    blockers: List[str] = []
    if candidate_manifest.get("schema_version") != "certification_candidate.v1":
        blockers.append("CANDIDATE_SCHEMA_INVALID")

    accounting = candidate_manifest.get("accounting")
    if not isinstance(accounting, Mapping):
        blockers.append("CERTIFICATION_ACCOUNTING_MISSING")
    else:
        inputs = _as_int(accounting.get("inputs", -1))
        included = _as_int(accounting.get("included", -1))
        excluded_validation = _as_int(
            accounting.get("excluded_validation_failure", -1)
        )
        excluded_certification = _as_int(
            accounting.get("excluded_certification_failure", -1)
        )
        if inputs != included + excluded_validation + excluded_certification:
            blockers.append("CERTIFICATION_ACCOUNTING_INCOMPLETE")
        if included <= 0:
            blockers.append("NO_CERTIFIABLE_ARTIFACTS")

    integrity = candidate_manifest.get("integrity")
    if not isinstance(integrity, Mapping):
        blockers.append("INTEGRITY_SUMMARY_MISSING")
    else:
        if integrity.get("validation_accounting_complete") is not True:
            blockers.append("VALIDATION_ACCOUNTING_INCOMPLETE")
        if integrity.get("sha256_manifest_recomputed") is not True:
            blockers.append("SHA256_MANIFEST_INVALID")
        if integrity.get("schema_and_provenance_complete") is not True:
            blockers.append("SCHEMA_OR_PROVENANCE_INCOMPLETE")
        if integrity.get("classification_lineage_complete") is not True:
            blockers.append("CLASSIFICATION_LINEAGE_INCOMPLETE")

    synthetic = candidate_manifest.get("test_synthetic_accounting")
    if not isinstance(synthetic, Mapping):
        blockers.append("TEST_SYNTHETIC_ACCOUNTING_MISSING")
    elif _as_int(synthetic.get("count", -1)) != 0:
        blockers.append("TEST_SYNTHETIC_CONTENT_PRESENT")
    if candidate_manifest.get("active_snapshot_promoted") is not False:
        blockers.append("ACTIVE_PROMOTION_NOT_PERMITTED")
    if candidate_manifest.get("query_serving_eligible") is not False:
        blockers.append("QUERY_SERVING_NOT_PERMITTED")

    unique_blockers = sorted(set(blockers))
    return {
        "promotion_blocked": bool(unique_blockers),
        "blockers": unique_blockers,
        "target_state": "QUARANTINED" if unique_blockers else "CERTIFIED",
    }


def certify_validation_report(
    storage_root: Path,
    certification_run_id: str,
    validation_report: Mapping[str, Any],
    *,
    completed_at: str,
) -> Dict[str, Any]:
    """Construct and persist an immutable non-ACTIVE candidate."""
    run_id = certification_run_id.strip()
    if not run_id:
        raise SnapshotCertificationError("certification_run_id is required")
    if validation_report.get("schema_version") != "artifact_validation_report.v1":
        raise SnapshotCertificationError(
            "H04 accepts only artifact_validation_report.v1"
        )
    if validation_report.get("active_snapshot_promoted") is not False:
        raise SnapshotCertificationError(
            "validation report cannot indicate active promotion"
        )
    dispositions = validation_report.get("dispositions")
    validation_accounting = validation_report.get("accounting")
    if not isinstance(dispositions, list) or not isinstance(
        validation_accounting, Mapping
    ):
        raise SnapshotCertificationError(
            "validation report lacks accounting or dispositions"
        )

    root = Path(storage_root)
    report_digest = _sha256(_canonical_bytes(dict(validation_report)))
    run_key = _sha256(run_id.encode("utf-8"))
    candidate_path = (
        root / "registry" / "certification_candidates" / (run_key + ".json")
    )
    if candidate_path.exists():
        existing = _load_json(candidate_path, "certification candidate")
        if existing.get("source_validation_report_digest") != report_digest:
            raise SnapshotCertificationError(
                "certification_run_id already exists with a different validation report"
            )
        return existing

    included: List[Dict[str, Any]] = []
    exclusions: List[Dict[str, Any]] = []
    validation_failed = 0
    certification_failed = 0
    classification_complete = True
    schema_and_provenance_complete = True
    test_synthetic_rows: List[str] = []

    for index, raw_row in enumerate(dispositions):
        if not isinstance(raw_row, Mapping):
            certification_failed += 1
            schema_and_provenance_complete = False
            exclusions.append(
                {
                    "input_index": index,
                    "reason": "VALIDATION_DISPOSITION_INVALID",
                    "stage": "CERTIFICATION",
                }
            )
            continue
        row = dict(raw_row)
        outcome = row.get("outcome")
        if outcome == "FAILED":
            validation_failed += 1
            exclusions.append(
                {
                    "input_index": index,
                    "source_artifact_id": row.get("source_artifact_id"),
                    "reason": row.get("failure_code", "VALIDATION_FAILED"),
                    "stage": "VALIDATION",
                }
            )
            continue
        if outcome != "VALIDATED":
            certification_failed += 1
            schema_and_provenance_complete = False
            exclusions.append(
                {
                    "input_index": index,
                    "source_artifact_id": row.get("source_artifact_id"),
                    "reason": "VALIDATION_OUTCOME_INVALID",
                    "stage": "CERTIFICATION",
                }
            )
            continue

        artifact, failures = _verify_validated_disposition(root, row)
        if failures or artifact is None:
            certification_failed += 1
            schema_and_provenance_complete = False
            if "CLASSIFICATION_LINEAGE_INCOMPLETE" in failures:
                classification_complete = False
            exclusions.append(
                {
                    "input_index": index,
                    "source_artifact_id": row.get("source_artifact_id"),
                    "reasons": failures,
                    "stage": "CERTIFICATION",
                }
            )
            continue
        classification = artifact["classification"]
        if classification.get("lineage_complete") is not True:
            classification_complete = False
        if classification.get("test_only") is True:
            test_synthetic_rows.append(str(artifact["derivative_artifact_id"]))
        included.append(artifact)

    included.sort(
        key=lambda item: (
            str(item["derivative_artifact_id"]),
            str(item["source_artifact_id"]),
        )
    )
    exclusions.sort(
        key=lambda item: (
            int(item.get("input_index", -1)),
            str(item.get("source_artifact_id") or ""),
        )
    )
    manifest_digest = _sha256(_canonical_bytes(included))

    reported_inputs = _as_int(validation_accounting.get("inputs", -1))
    reported_validated = _as_int(validation_accounting.get("validated", -1))
    reported_failed = _as_int(validation_accounting.get("failed", -1))
    counted_validated = sum(
        1
        for row in dispositions
        if isinstance(row, Mapping) and row.get("outcome") == "VALIDATED"
    )
    counted_failed = sum(
        1
        for row in dispositions
        if isinstance(row, Mapping) and row.get("outcome") == "FAILED"
    )
    validation_accounting_complete = (
        reported_inputs == len(dispositions)
        and reported_inputs == reported_validated + reported_failed
        and reported_validated == counted_validated
        and reported_failed == counted_failed
    )

    candidate = {
        "schema_version": "certification_candidate.v1",
        "certification_run_id": run_id,
        "candidate_id": "candidate-sha256-" + run_key,
        "source_validation_run_id": str(
            validation_report.get("validation_run_id") or ""
        ),
        "source_validation_report_digest": report_digest,
        "completed_at": completed_at,
        "sha256_manifest": manifest_digest,
        "artifact_count": len(included),
        "artifacts": included,
        "exclusion_ledger": exclusions,
        "accounting": {
            "inputs": len(dispositions),
            "included": len(included),
            "excluded_validation_failure": validation_failed,
            "excluded_certification_failure": certification_failed,
        },
        "test_synthetic_accounting": {
            "count": len(test_synthetic_rows),
            "artifact_ids": sorted(test_synthetic_rows),
        },
        "integrity": {
            "validation_accounting_complete": validation_accounting_complete,
            "sha256_manifest_recomputed": True,
            "schema_and_provenance_complete": schema_and_provenance_complete,
            "classification_lineage_complete": classification_complete,
        },
        "active_snapshot_promoted": False,
        "query_serving_eligible": False,
        "answer_eligible": False,
        "citation_eligible": False,
    }
    gate = compute_snapshot_gate(candidate)
    candidate["certification_decision"] = gate
    candidate["state"] = gate["target_state"]
    _write_json_once(candidate_path, candidate)
    return candidate


def snapshot_operation_decision(
    certification_candidate: Mapping[str, Any], operation: str
) -> Dict[str, Any]:
    """Decide access without executing retrieval or query answering."""
    normalized = operation.strip().upper()
    if normalized in {"OPERATIONAL_STATUS", "PROVISIONAL_METADATA"}:
        return {
            "allowed": True,
            "operation": normalized,
            "provisional_only": True,
            "reason": "pre-certification operational surface",
        }
    state = str(certification_candidate.get("state") or "")
    active = (
        state == "ACTIVE"
        and certification_candidate.get("query_serving_eligible") is True
    )
    if normalized in {"ANSWER", "CITATION"} and not active:
        return {
            "allowed": False,
            "operation": normalized,
            "provisional_only": False,
            "reason": "PRE_CERTIFICATION_USE_DENIED",
        }
    if not active:
        return {
            "allowed": False,
            "operation": normalized,
            "provisional_only": False,
            "reason": "NON_ACTIVE_SNAPSHOT_DENIED",
        }
    return {
        "allowed": True,
        "operation": normalized,
        "provisional_only": False,
        "reason": "ACTIVE_SNAPSHOT_POLICY_ONLY",
    }
