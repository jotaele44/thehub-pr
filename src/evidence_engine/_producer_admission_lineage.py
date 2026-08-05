"""Pure H07 producer-package lineage and admission decision."""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from ._producer_admission_accounting import (
    _build_decision,
    _validate_file_accounting,
    _validate_source_accounting,
)
from ._producer_admission_entries import _validate_lineage_entries
from ._producer_admission_identity import _validate_identity_bindings
from ._producer_admission_common import _mapping


def compute_producer_package_admission_decision(
    job_record: Mapping[str, Any],
    run_receipt: Mapping[str, Any],
    package_manifest: Mapping[str, Any],
    lineage_manifest: Mapping[str, Any],
    file_report: Mapping[str, Any],
) -> Dict[str, Any]:
    """Purely evaluate supplied H06 records, lineage, and file observations."""
    context = _validate_identity_bindings(
        job_record, run_receipt, package_manifest, lineage_manifest
    )
    reasons: List[str] = list(context["reasons"])
    entry_result = _validate_lineage_entries(
        context["package_map"], context["lineage_map"], context["source_map"]
    )
    entry_faults = entry_result["entry_faults"]
    source_accounting = _validate_source_accounting(
        context["source_map"],
        _mapping(context["lineage"]).get("source_dispositions"),
        entry_result["referenced_sources"],
    )
    reasons.extend(source_accounting["reasons"])
    reasons.extend(
        _validate_file_accounting(
            context["package_map"], _mapping(file_report), entry_faults
        )
    )
    reasons.extend(reason for faults in entry_faults.values() for reason in faults)
    return _build_decision(context, reasons, entry_faults, source_accounting)


__all__ = ["compute_producer_package_admission_decision"]
