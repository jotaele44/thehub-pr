"""Fail-closed invariants for temporal CI attestations.

This module does not replace domain certification_state fields. It prevents
historical CI evidence from being promoted across SHA/environment boundaries.
"""
from __future__ import annotations
from typing import Any, Mapping

class TemporalAttestationError(ValueError):
    pass

def validate_temporal_attestation(row: Mapping[str, Any]) -> None:
    execution = row.get("execution_state")
    test = row.get("test_state")
    if execution == "NONEXECUTED" and test != "NOT_RUN":
        raise TemporalAttestationError("nonexecuted_requires_test_not_run")
    if test in {"PASS", "FAIL"} and execution != "EXECUTED":
        raise TemporalAttestationError("test_result_requires_execution")

def may_inherit_pass(prior: Mapping[str, Any], current: Mapping[str, Any]) -> bool:
    validate_temporal_attestation(prior)
    validate_temporal_attestation(current)
    return bool(
        prior.get("test_state") == "PASS"
        and prior.get("execution_state") == "EXECUTED"
        and prior.get("source_sha")
        and prior.get("source_sha") == current.get("source_sha")
        and prior.get("environment") == current.get("environment")
        and prior.get("certification_scope") == current.get("certification_scope")
    )

def coexist_without_contradiction(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    """Different time/environment/manifestation/scope observations may coexist."""
    dimensions = ("environment", "manifestation_id", "valid_at", "certification_scope")
    return any(a.get(key) != b.get(key) for key in dimensions)
