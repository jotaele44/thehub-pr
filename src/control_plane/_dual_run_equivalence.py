"""Versioned field-level model equivalence for H08."""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, Mapping, Sequence, Tuple

from ._dual_run_common import DualRunReadinessError, as_mapping, numeric, sha256_json, unique_index

_ALLOWED = {
    "EXACT_CANONICAL",
    "NORMALIZED_TEXT_EQUAL",
    "ENUM_EXACT",
    "SET_EQUAL",
    "NUMERIC_ABSOLUTE_TOLERANCE",
    "NUMERIC_RELATIVE_TOLERANCE",
    "TIMESTAMP_TOLERANCE",
    "GEOSPATIAL_DISTANCE_TOLERANCE",
}
_PROVENANCE_PINS = (
    "source_artifact_id",
    "source_sha256",
    "provider_id",
    "model_id",
    "model_revision",
    "prompt_template_hash",
    "policy_version",
    "access_context_hash",
    "extraction_schema_version",
)


def validate_policy_rules(policy: Mapping[str, Any], required_fields: Sequence[str]) -> Dict[str, Mapping[str, Any]]:
    rules = [as_mapping(item, "policy rule") for item in policy.get("rules", [])]
    indexed = unique_index(rules, "field_key", "policy rule")
    for key, rule in indexed.items():
        if "*" in key or key.strip() in {"", "*"}:
            raise DualRunReadinessError("wildcard model-field rules are prohibited")
        comparator = str(rule.get("comparator") or "")
        if comparator not in _ALLOWED:
            raise DualRunReadinessError(f"prohibited or unknown comparator: {comparator}")
        parameters = as_mapping(rule.get("parameters", {}), "rule parameters")
        if comparator in {
            "NUMERIC_ABSOLUTE_TOLERANCE",
            "NUMERIC_RELATIVE_TOLERANCE",
            "TIMESTAMP_TOLERANCE",
            "GEOSPATIAL_DISTANCE_TOLERANCE",
        }:
            tolerance = numeric(parameters.get("tolerance"), "tolerance")
            if tolerance < 0:
                raise DualRunReadinessError("tolerance must be non-negative")
    required = set(required_fields)
    if set(indexed) != required:
        missing = sorted(required - set(indexed))
        additional = sorted(set(indexed) - required)
        raise DualRunReadinessError(
            f"model-field policy coverage mismatch; missing={missing}, additional={additional}"
        )
    return indexed


def _parse_timestamp(value: Any) -> float:
    if not isinstance(value, str):
        raise DualRunReadinessError("timestamp comparator requires strings")
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError as exc:
        raise DualRunReadinessError("invalid timestamp value") from exc


def _geospatial_distance_m(a: Any, b: Any) -> float:
    ma = as_mapping(a, "geospatial value")
    mb = as_mapping(b, "geospatial value")
    lat1, lon1 = math.radians(numeric(ma.get("lat"), "lat")), math.radians(numeric(ma.get("lon"), "lon"))
    lat2, lon2 = math.radians(numeric(mb.get("lat"), "lat")), math.radians(numeric(mb.get("lon"), "lon"))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    hav = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371008.8 * 2 * math.atan2(math.sqrt(hav), math.sqrt(1 - hav))


def compare_values(left: Any, right: Any, rule: Mapping[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    comparator = str(rule["comparator"])
    parameters = as_mapping(rule.get("parameters", {}), "parameters")
    if comparator in {"EXACT_CANONICAL", "ENUM_EXACT"}:
        return sha256_json(left) == sha256_json(right), {"left": left, "right": right}
    if comparator == "NORMALIZED_TEXT_EQUAL":
        if not isinstance(left, str) or not isinstance(right, str):
            raise DualRunReadinessError("text comparator requires strings")
        lv = " ".join(left.casefold().split())
        rv = " ".join(right.casefold().split())
        return lv == rv, {"left_normalized": lv, "right_normalized": rv}
    if comparator == "SET_EQUAL":
        if not isinstance(left, list) or not isinstance(right, list):
            raise DualRunReadinessError("set comparator requires arrays")
        lv = sorted(sha256_json(item) for item in left)
        rv = sorted(sha256_json(item) for item in right)
        return lv == rv, {"left_normalized": lv, "right_normalized": rv}
    tolerance = numeric(parameters.get("tolerance"), "tolerance")
    if comparator == "NUMERIC_ABSOLUTE_TOLERANCE":
        delta = abs(numeric(left, "left") - numeric(right, "right"))
        return delta <= tolerance, {"delta": delta, "tolerance": tolerance}
    if comparator == "NUMERIC_RELATIVE_TOLERANCE":
        lv, rv = numeric(left, "left"), numeric(right, "right")
        denominator = max(abs(lv), abs(rv), 1e-15)
        delta = abs(lv - rv) / denominator
        return delta <= tolerance, {"relative_delta": delta, "tolerance": tolerance}
    if comparator == "TIMESTAMP_TOLERANCE":
        delta = abs(_parse_timestamp(left) - _parse_timestamp(right))
        return delta <= tolerance, {"seconds_delta": delta, "tolerance": tolerance}
    if comparator == "GEOSPATIAL_DISTANCE_TOLERANCE":
        delta = _geospatial_distance_m(left, right)
        return delta <= tolerance, {"distance_m": delta, "tolerance": tolerance}
    raise DualRunReadinessError(f"unsupported comparator: {comparator}")


def provenance_equal(left: Mapping[str, Any], right: Mapping[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    mismatches = {
        key: {"legacy": left.get(key), "candidate": right.get(key)}
        for key in _PROVENANCE_PINS
        if left.get(key) != right.get(key)
    }
    return not mismatches, mismatches
