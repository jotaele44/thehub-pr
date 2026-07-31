"""H07 source, file, terminal-disposition, and decision accounting."""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Set

from ._producer_admission_common import _mapping


def _validate_source_accounting(
    source_map: Mapping[str, Mapping[str, Any]],
    source_dispositions: Any,
    referenced_sources: Set[str],
) -> Dict[str, Any]:
    reasons: List[str] = []
    items = [dict(item) for item in source_dispositions if isinstance(item, Mapping)] if isinstance(source_dispositions, list) else []
    disposition_map = {str(item.get("artifact_id") or ""): item for item in items}
    source_ids = set(source_map)
    if len(disposition_map) != len(items) or set(disposition_map) != source_ids:
        reasons.append("SOURCE_ACCOUNTING_INCOMPLETE")
    used_ids = {
        source_id for source_id, item in disposition_map.items()
        if item.get("disposition") == "USED"
    }
    if used_ids != referenced_sources:
        reasons.append("SOURCE_USAGE_ACCOUNTING_MISMATCH")
    for item in disposition_map.values():
        disposition = item.get("disposition")
        if disposition not in {"USED", "EXCLUDED", "FAILED"}:
            reasons.append("SOURCE_DISPOSITION_INVALID")
        if disposition in {"EXCLUDED", "FAILED"} and not str(item.get("reason_code") or ""):
            reasons.append("SOURCE_DISPOSITION_REASON_REQUIRED")
    used = sum(item.get("disposition") == "USED" for item in disposition_map.values())
    excluded = sum(item.get("disposition") == "EXCLUDED" for item in disposition_map.values())
    failed = sum(item.get("disposition") == "FAILED" for item in disposition_map.values())
    complete = (
        len(source_ids) == used + excluded + failed
        and set(disposition_map) == source_ids
    )
    if not complete:
        reasons.append("SOURCE_ACCOUNTING_INCOMPLETE")
    return {
        "reasons": sorted(set(reasons)),
        "source_ids": source_ids,
        "disposition_map": disposition_map,
        "used": used,
        "excluded": excluded,
        "failed": failed,
        "complete": complete,
    }


def _validate_file_accounting(
    package_map: Mapping[str, Mapping[str, Any]],
    files: Mapping[str, Any],
    entry_faults: Dict[str, List[str]],
) -> List[str]:
    reasons: List[str] = []
    entries = [dict(item) for item in files.get("entries", []) if isinstance(item, Mapping)]
    file_map = {str(item.get("output_id") or ""): item for item in entries}
    if (
        files.get("root_valid") is not True
        or files.get("package_failures") not in ([], None)
        or len(file_map) != len(entries)
        or set(file_map) != set(package_map)
    ):
        reasons.append("PACKAGE_FILE_BOUNDARY_INVALID")
    for output_id, package_entry in package_map.items():
        observation = _mapping(file_map.get(output_id))
        faults = list(entry_faults.get(output_id, []))
        if (
            observation.get("verified") is not True
            or observation.get("actual_sha256") != package_entry.get("sha256")
            or observation.get("actual_size_bytes") != package_entry.get("size_bytes")
            or observation.get("relative_path") != package_entry.get("relative_path")
        ):
            faults.extend(
                str(item)
                for item in observation.get(
                    "failure_codes", ["PACKAGE_FILE_VERIFICATION_FAILED"]
                )
            )
            if not faults:
                faults.append("PACKAGE_FILE_VERIFICATION_FAILED")
        if faults:
            entry_faults[output_id] = sorted(set(faults))
    return reasons


def _build_decision(
    context: Mapping[str, Any],
    reasons: List[str],
    entry_faults: Mapping[str, List[str]],
    source_accounting: Mapping[str, Any],
) -> Dict[str, Any]:
    job = _mapping(context.get("job"))
    run = _mapping(context.get("run"))
    package = _mapping(context.get("package"))
    lineage = _mapping(context.get("lineage"))
    package_map = _mapping(context.get("package_map"))
    reasons = sorted(set(reasons))
    accepted = not reasons
    dispositions: List[Dict[str, Any]] = []
    admitted = excluded = failed = 0
    for output_id in sorted(package_map):
        faults = list(entry_faults.get(output_id, []))
        if accepted:
            status, codes = "ELIGIBLE", []
            admitted += 1
        elif faults:
            status, codes = "FAILED", faults
            failed += 1
        else:
            status, codes = "EXCLUDED", ["PACKAGE_ATOMIC_DENIAL"]
            excluded += 1
        dispositions.append({"output_id": output_id, "disposition": status, "reason_codes": codes})
    return {
        "schema_version": "producer_package_admission_decision.v1",
        "decision": "ACCEPTED" if accepted else "DENIED",
        "accepted": accepted,
        "reason_codes": reasons,
        "job_spec_id": job.get("job_spec_id"),
        "producer_run_receipt_id": run.get("producer_run_receipt_id"),
        "producer_package_id": package.get("producer_package_id"),
        "package_sha256": package.get("package_sha256"),
        "lineage_manifest_id": lineage.get("lineage_manifest_id"),
        "authorization_reference": run.get("authorization_reference"),
        "audit_event_reference": run.get("audit_event_reference"),
        "entry_accounting": {
            "expected": len(package_map), "admitted": admitted if accepted else 0,
            "excluded": excluded, "failed": failed,
            "complete": len(package_map) == (admitted if accepted else 0) + excluded + failed,
        },
        "source_accounting": {
            "expected": len(source_accounting.get("source_ids", set())),
            "used": source_accounting.get("used", 0),
            "excluded": source_accounting.get("excluded", 0),
            "failed": source_accounting.get("failed", 0),
            "complete": source_accounting.get("complete") is True,
        },
        "dispositions": dispositions,
        "secret_material_serialized": False,
        "acquisition_receipt_used": False,
        "certified_state_created": False,
        "active_snapshot_promoted": False,
        "answer_eligible": False,
        "claim_eligible": False,
        "retrieval_eligible": False,
        "citation_eligible": False,
    }


__all__ = ["_build_decision", "_validate_file_accounting", "_validate_source_accounting"]
