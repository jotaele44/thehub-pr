"""Immutable H08 receipt construction and gate-evidence projection."""
from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence

from ._dual_run_common import sha256_json


def comparison_receipt_id(payload: Mapping[str, Any]) -> str:
    body = dict(payload)
    body.pop("comparison_receipt_id", None)
    return "dual-run-comparison-sha256-" + sha256_json(body)


def readiness_receipt_id(payload: Mapping[str, Any]) -> str:
    body = dict(payload)
    body.pop("readiness_receipt_id", None)
    return "dual-run-readiness-sha256-" + sha256_json(body)


def build_gate_evidence_projection(
    readiness: Mapping[str, Any],
    lane_receipts: Sequence[Mapping[str, Any]],
    evaluated_at: str,
) -> Dict[str, Any]:
    derived = [
        {
            "run_id": str(item["run_id"]),
            "receipt_sha256": str(item["receipt_sha256"]),
            "signature_verified": True,
        }
        for item in lane_receipts
    ]
    dual_passed = readiness.get("dual_run_gate_status") == "passed"
    return {
        "schema_version": "prii_gate_evidence_v2",
        "profile_id": "adr0006_dual_run_readiness",
        "profile_scope": "H08 dual-run evidence only; retirement remains separately blocked.",
        "evaluated_at": evaluated_at,
        "policy_sha256": str(readiness["equivalence_policy_sha256"]),
        "gates": [
            {
                "gate_id": "G01_ADR0006_DUAL_RUN_PARITY",
                "requirement": "At least two complete equivalent shadow trial pairs.",
                "blocking": True,
                "status": "passed" if dual_passed else "failed",
                "status_reason": str(readiness.get("status_reason") or ""),
                "derived_from": derived if dual_passed else [],
                "attested_by": [],
                "annotations": [],
            },
            {
                "gate_id": "G02_ADR0006_RETIREMENT_AUTHORIZATION",
                "requirement": "Retirement requires later GUI, disposition, consumer, provider-removal and deny-network gates.",
                "blocking": True,
                "status": "deferred",
                "status_reason": "H08 never authorizes retirement.",
                "derived_from": [],
                "attested_by": [],
                "annotations": [],
            },
        ],
    }
