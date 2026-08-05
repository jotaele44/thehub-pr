"""H07 per-output lineage validation."""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Set

from ._producer_admission_common import _mapping
from ._producer_admission_metadata import (
    _classification_reasons,
    _validate_model_fields,
    _validate_satim_signal,
)


def _validate_lineage_entries(
    package_map: Mapping[str, Mapping[str, Any]],
    lineage_map: Mapping[str, Mapping[str, Any]],
    source_map: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    entry_faults: Dict[str, List[str]] = {}
    referenced_sources: Set[str] = set()
    for output_id in sorted(package_map):
        faults: List[str] = []
        package_entry = package_map[output_id]
        lineage_entry = _mapping(lineage_map.get(output_id))
        if not lineage_entry:
            entry_faults[output_id] = ["MISSING_OUTPUT_LINEAGE"]
            continue
        if lineage_entry.get("output_sha256") != package_entry.get("sha256"):
            faults.append("LINEAGE_OUTPUT_SHA_MISMATCH")
        source_ids_raw = lineage_entry.get("source_artifact_ids")
        source_ids = (
            {str(item) for item in source_ids_raw}
            if isinstance(source_ids_raw, list)
            else set()
        )
        source_items = [
            source_map[source_id]
            for source_id in sorted(source_ids)
            if source_id in source_map
        ]
        if not source_ids or len(source_items) != len(source_ids):
            faults.append("UNKNOWN_SOURCE_ARTIFACT")
        referenced_sources.update(source_ids)
        faults.extend(
            _classification_reasons(
                _mapping(lineage_entry.get("classification")),
                source_items,
            )
        )
        derivation = str(lineage_entry.get("derivation_kind") or "")
        model_fields = lineage_entry.get("model_field_provenance")
        satim_signal = lineage_entry.get("satim_signal")
        if derivation == "MODEL_DERIVED":
            faults.extend(_validate_model_fields(model_fields, source_map, source_ids))
            if satim_signal not in (None, {}):
                faults.append("MODEL_OUTPUT_HAS_SATIM_SIGNAL")
        elif derivation == "SATIM_PROVISIONAL":
            faults.extend(_validate_satim_signal(satim_signal, source_ids))
            if model_fields not in (None, []):
                faults.append("SATIM_OUTPUT_HAS_MODEL_FIELDS")
        elif derivation == "DETERMINISTIC":
            if model_fields not in (None, []):
                faults.append("DETERMINISTIC_OUTPUT_HAS_MODEL_FIELDS")
            if satim_signal not in (None, {}):
                faults.append("DETERMINISTIC_OUTPUT_HAS_SATIM_SIGNAL")
        else:
            faults.append("DERIVATION_KIND_INVALID")
        if any(
            not str(lineage_entry.get(key) or "")
            for key in (
                "method", "method_version", "output_schema_id",
                "output_schema_version",
            )
        ):
            faults.append("DERIVATION_METADATA_INCOMPLETE")
        if faults:
            entry_faults[output_id] = sorted(set(faults))
    return {
        "entry_faults": entry_faults,
        "referenced_sources": referenced_sources,
    }


__all__ = ["_validate_lineage_entries"]
