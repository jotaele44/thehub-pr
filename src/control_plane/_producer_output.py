"""H06 producer output, accounting, and package-manifest verification helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from ._producer_common import (
    _canonical_bytes, _is_sha256, _mapping, _nonempty, _path_within, _safe_relative_path, _sha256,
)

def _account_inputs(
    expected_ids: Set[str],
    report: Mapping[str, Any],
    reasons: List[str],
) -> Dict[str, Any]:
    processed_raw = report.get("processed_inputs")
    excluded_raw = report.get("excluded_inputs")
    failed_raw = report.get("failed_inputs")
    processed = [str(item) for item in processed_raw] if isinstance(processed_raw, list) else []
    excluded = [dict(item) for item in excluded_raw if isinstance(item, Mapping)] if isinstance(excluded_raw, list) else []
    failed = [dict(item) for item in failed_raw if isinstance(item, Mapping)] if isinstance(failed_raw, list) else []
    excluded_ids = [str(item.get("artifact_id") or "") for item in excluded]
    failed_ids = [str(item.get("artifact_id") or "") for item in failed]
    all_ids = processed + excluded_ids + failed_ids
    valid_reasons = all(_nonempty(item.get("reason_code")) for item in excluded)
    valid_failures = all(_nonempty(item.get("failure_code")) for item in failed)
    complete = (
        len(all_ids) == len(set(all_ids))
        and set(all_ids) == expected_ids
        and valid_reasons
        and valid_failures
    )
    if not complete:
        reasons.append("INPUT_ACCOUNTING_INCOMPLETE")
    return {
        "expected": len(expected_ids),
        "processed": len(processed),
        "excluded": len(excluded),
        "failed": len(failed),
        "complete": complete,
        "processed_inputs": sorted(processed),
        "excluded_inputs": sorted(excluded, key=lambda item: str(item.get("artifact_id"))),
        "failed_inputs": sorted(failed, key=lambda item: str(item.get("artifact_id"))),
    }

def _output_partition(
    required_ids: Set[str],
    report: Mapping[str, Any],
    reasons: List[str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], bool]:
    outputs_raw = report.get("outputs")
    failures_raw = report.get("output_failures")
    outputs = [dict(item) for item in outputs_raw if isinstance(item, Mapping)] if isinstance(outputs_raw, list) else []
    failures = [dict(item) for item in failures_raw if isinstance(item, Mapping)] if isinstance(failures_raw, list) else []
    output_ids = [str(item.get("output_id") or "") for item in outputs]
    failure_ids = [str(item.get("output_id") or "") for item in failures]
    all_ids = output_ids + failure_ids
    valid_failures = all(_nonempty(item.get("failure_code")) for item in failures)
    complete = (
        len(all_ids) == len(set(all_ids))
        and set(all_ids) == required_ids
        and valid_failures
    )
    if not complete:
        reasons.append("OUTPUT_ACCOUNTING_INCOMPLETE")
    outputs.sort(key=lambda item: str(item.get("output_id")))
    failures.sort(key=lambda item: str(item.get("output_id")))
    return outputs, failures, complete

def _verify_outputs(
    output_root: Path,
    write_root: str,
    outputs: Iterable[Mapping[str, Any]],
    limits: Mapping[str, int],
    reasons: List[str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int, int]:
    verified: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []
    output_items = [dict(item) for item in outputs]
    declared_paths = {str(item.get("relative_path") or "") for item in output_items}
    root_ok = (
        output_root.is_dir()
        and not output_root.is_symlink()
        and output_root.name == write_root
    )
    observed_bytes = 0
    observed_files = 0
    if root_ok:
        for candidate in output_root.rglob("*"):
            if candidate.is_symlink():
                reasons.append("OUTPUT_SYMLINK_DENIED")
                continue
            if candidate.is_file():
                relative = candidate.relative_to(output_root).as_posix()
                observed_files += 1
                try:
                    observed_bytes += candidate.stat().st_size
                except OSError:
                    reasons.append("OUTPUT_STAT_FAILED")
                if relative not in declared_paths:
                    reasons.append("UNDECLARED_OUTPUT_FILE")
    seen_paths: Set[str] = set()
    for raw in output_items:
        output_id = str(raw.get("output_id") or "")
        relative_path = str(raw.get("relative_path") or "")
        failure_code: Optional[str] = None
        if not root_ok:
            failure_code = "DESIGNATED_OUTPUT_DIRECTORY_MISMATCH"
        elif relative_path in seen_paths:
            failure_code = "OUTPUT_PATH_DUPLICATE"
        else:
            seen_paths.add(relative_path)
            path = _path_within(output_root, relative_path)
            if path is None:
                failure_code = "OUTPUT_PATH_ESCAPE_DENIED"
            else:
                try:
                    data = path.read_bytes()
                except OSError:
                    failure_code = "OUTPUT_READ_FAILED"
                else:
                    digest = _sha256(data)
                    size = len(data)
                    if raw.get("sha256") != digest or raw.get("size_bytes") != size:
                        failure_code = "OUTPUT_DIGEST_OR_SIZE_MISMATCH"
                    elif size > limits.get("max_file_bytes", 0):
                        failure_code = "RESOURCE_FILE_BYTES_LIMIT_EXCEEDED"
                    else:
                        verified.append(
                            {
                                "output_id": output_id,
                                "relative_path": relative_path,
                                "sha256": digest,
                                "size_bytes": size,
                            }
                        )
        if failure_code:
            reasons.append(failure_code)
            failures.append(
                {
                    "output_id": output_id,
                    "relative_path": relative_path,
                    "failure_code": failure_code,
                }
            )
    return verified, failures, observed_bytes, observed_files

def _resource_accounting(
    decision: Mapping[str, Any],
    report: Mapping[str, Any],
    observed_output_bytes: int,
    observed_output_files: int,
    reasons: List[str],
) -> Dict[str, Any]:
    limits = _mapping(decision.get("resource_limits"))
    duration = report.get("duration_seconds")
    if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration < 0:
        reasons.append("RUN_DURATION_INVALID")
        duration_value = 0.0
    else:
        duration_value = float(duration)
    input_bytes = int(_mapping(decision.get("inputs")).get("total_bytes") or 0)
    output_bytes = observed_output_bytes
    output_files = observed_output_files
    violations: List[str] = []
    if duration_value > int(limits.get("max_duration_seconds") or 0):
        violations.append("RESOURCE_DURATION_LIMIT_EXCEEDED")
    if input_bytes > int(limits.get("max_input_bytes") or 0):
        violations.append("RESOURCE_INPUT_BYTES_LIMIT_EXCEEDED")
    if output_bytes > int(limits.get("max_output_bytes") or 0):
        violations.append("RESOURCE_OUTPUT_BYTES_LIMIT_EXCEEDED")
    if output_files > int(limits.get("max_output_files") or 0):
        violations.append("RESOURCE_OUTPUT_FILE_LIMIT_EXCEEDED")
    reasons.extend(violations)
    return {
        "limits": limits,
        "measured": {
            "duration_seconds": duration_value,
            "input_bytes": input_bytes,
            "output_bytes": output_bytes,
            "output_files": output_files,
        },
        "violations": sorted(set(violations)),
    }

def _package_manifest(
    decision: Mapping[str, Any],
    verified_outputs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    body = {
        "job_spec_id": decision.get("job_spec_id"),
        "job_spec_sha256": decision.get("signed_payload_sha256"),
        "producer": "skywatcher-pr",
        "producer_revision": decision.get("producer_revision"),
        "worker_profile": _mapping(decision.get("pins")).get("worker_profile"),
        "schema_revisions": _mapping(decision.get("pins")).get("schema_revisions"),
        "entries": sorted(
            verified_outputs, key=lambda item: (item["output_id"], item["relative_path"])
        ),
    }
    digest = _sha256(_canonical_bytes(body))
    return {
        "schema_version": "producer_package_manifest.v1",
        "producer_package_id": "producer-package-sha256-" + digest,
        "package_sha256": digest,
        **body,
        "active_snapshot_promoted": False,
        "query_serving_eligible": False,
    }

__all__ = [
    "_account_inputs", "_output_partition", "_package_manifest",
    "_resource_accounting", "_verify_outputs",
]
