from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timezone

from .classifier import classify_observations


CASES = [
    ("ui-no-op", {"handler_bound": False}, "UI_NO_OP"),
    ("partially-wired", {"handler_bound": True, "handler_resolved": True, "intent_observed": True}, "PARTIALLY_WIRED"),
    ("target-missing", {"handler_bound": True, "handler_resolved": False}, "TARGET_MISSING"),
    ("contract-mismatch", {"handler_bound": True, "handler_resolved": True, "contract_mismatch": True}, "CONTRACT_MISMATCH"),
    ("wired-but-blocked", {"handler_bound": True, "handler_resolved": True, "blocked_precondition": True}, "WIRED_BUT_BLOCKED"),
    ("executable-by-contract", {"handler_bound": True, "handler_resolved": True, "boundary_reached": True, "contract_matched": True, "side_effect_intercepted": True}, "EXECUTABLE_BY_CONTRACT"),
]

FIXTURE_REPOSITORY = "fixture/federation-audit"
FIXTURE_COMMIT = hashlib.sha1(b"federation-audit-fixture-v0.1", usedforsecurity=False).hexdigest()


def _node(case_id: str, kind: str, status: str, source: str | None = None) -> dict:
    node_id = hashlib.sha256(f"{case_id}:{kind}:{status}".encode()).hexdigest()[:24]
    return {"node_id": node_id, "kind": kind, "status": status, "source": source}


def _path(case_id: str, observations: dict) -> list[dict]:
    source = "playwright/fixtures/index.html"
    path = [_node(case_id, "gui-control", "observed", source)]
    if not observations.get("handler_bound", False):
        path.append(_node(case_id, "event-handler", "missing", source))
        return path
    if not observations.get("handler_resolved", False):
        path.append(_node(case_id, "event-handler", "missing", source))
        return path
    path.append(_node(case_id, "event-handler", "resolved", source))
    if observations.get("contract_mismatch"):
        path.append(_node(case_id, "declared-contract", "failed", source))
    elif observations.get("blocked_precondition"):
        path.append(_node(case_id, "dependency", "blocked", source))
    elif observations.get("boundary_reached") and observations.get("contract_matched"):
        path.append(_node(case_id, "intercepted-boundary", "terminal", source))
    elif observations.get("intent_observed"):
        path.append(_node(case_id, "application-intent", "observed", source))
    return path


def run_fixture_audit() -> dict:
    traces = []
    for case_id, observations, expected in CASES:
        classification, confidence, fault_boundary, recommended_fix = classify_observations(observations)
        passed = classification.value == expected
        trace_id = hashlib.sha256(f"fixture:{case_id}".encode()).hexdigest()[:24]
        traces.append({
            "trace_id": trace_id,
            "repository": FIXTURE_REPOSITORY,
            "commit": FIXTURE_COMMIT,
            "surface": {
                "kind": "gui-control",
                "id": case_id,
                "label": case_id.replace("-", " ").title(),
                "source": "playwright/fixtures/index.html",
                "line": None,
            },
            "path": _path(case_id, observations),
            "observations": {
                **observations,
                "expected_classification": expected,
                "fixture_case_passed": passed,
                "production_side_effects": False,
            },
            "classification": classification.value,
            "fault_boundary": fault_boundary,
            "confidence": confidence,
            "evidence": [{
                "tier": "T2",
                "kind": "deterministic-controlled-fixture",
                "locator": f"fixture:{case_id}",
                "digest": None,
            }],
            "recommended_fix": recommended_fix,
        })

    counts = Counter(trace["classification"] for trace in traces)
    return {
        "schema_version": "0.1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "traces": traces,
        "coverage": {
            "surfaces_discovered": len(traces),
            "surfaces_classified": len(traces),
            "t1_or_t2_supported": len(traces),
            "by_kind": {"gui-control": len(traces)},
            "classification_counts": dict(sorted(counts.items())),
            "repositories_present": 1,
            "repositories_missing": 0,
        },
        "workspace_gaps": [],
    }


def fixture_passed(ledger: dict) -> bool:
    return bool(ledger["traces"]) and all(
        trace["observations"].get("fixture_case_passed") is True
        for trace in ledger["traces"]
    )
