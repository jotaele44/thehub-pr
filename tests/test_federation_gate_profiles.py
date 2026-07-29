"""Gate profiles, merge readiness, and the checks that produce attestations.

A profile narrows what a gate set measures. That is a useful thing and also a
dangerous one: narrowing scope is exactly how an incomplete result gets made to
look finished. These tests exist to pin the properties that keep it honest --
the wider profile is still evaluated and published, exemptions are enumerated
rather than inferred from prose, and a gate cannot be excused by writing a
reason into it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

pytest.importorskip("cryptography")

from tools.build_operations_policy import (  # noqa: E402
    KNOWN_ROLLBACK_STRATEGIES,
    validate_rollback_strategy,
)
from tools.emit_gate_attestations import (  # noqa: E402
    check_enabled_rollback_coverage,
    check_no_deletion_capability,
    implemented_rollback_strategies,
)
from tools.evaluate_federation_gates import (  # noqa: E402
    FEDERATION_VECTOR_RULES,
    GATING_PROFILE,
    HUB_SLICE_OUT_OF_SCOPE,
    HUB_SLICE_RULES,
    MERGE_TIME_VERIFIED,
    PROFILES,
    merge_readiness,
)

POLICY = json.loads(
    (REPO_ROOT / "config" / "operations_policy.json").read_text(encoding="utf-8")
)["policy"]["operations"]


# ── profiles cover the same gates, and say so ───────────────────────────────


def test_both_profiles_cover_every_gate():
    """Narrowing scope must not drop a gate; it may only restate one."""
    assert {rule.gate_id for rule in HUB_SLICE_RULES} == {
        rule.gate_id for rule in FEDERATION_VECTOR_RULES
    }


def test_the_gating_profile_is_the_narrow_one():
    assert GATING_PROFILE == "hub_slice"
    assert GATING_PROFILE in PROFILES


def test_the_vector_profile_still_records_the_macos_gates_as_blocked():
    """The wider profile must not inherit the narrow one's optimism."""
    blocked = {
        rule.gate_id for rule in FEDERATION_VECTOR_RULES if rule.blocked_reason
    }
    assert blocked == {
        "G07_NATIVE_SECRETS",
        "G15_7_OF_7_UI_SETUP",
        "G16_7_OF_7_UI_VALIDATION",
        "G22_REAL_OPERATOR_MACOS",
    }


def test_the_hub_profile_makes_those_gates_attestable_instead_of_blocked():
    by_id = {rule.gate_id: rule for rule in HUB_SLICE_RULES}
    for gate_id in ("G07_NATIVE_SECRETS", "G15_7_OF_7_UI_SETUP", "G22_REAL_OPERATOR_MACOS"):
        assert by_id[gate_id].blocked_reason == ""
        assert by_id[gate_id].required_attestations


def test_producer_gate_stays_deferred_in_the_hub_profile():
    """G17 cannot be restated at Hub scope without changing what it measures."""
    by_id = {rule.gate_id: rule for rule in HUB_SLICE_RULES}
    assert by_id["G17_6_OF_6_PRODUCER_EXPORTS"].deferred_reason


# ── merge readiness ─────────────────────────────────────────────────────────


def _evidence(*gates):
    return {"profile_id": "hub_slice", "gates": list(gates)}


def gate(gate_id, status, blocking=True):
    return {"gate_id": gate_id, "status": status, "blocking": blocking, "derived_from": []}


def test_all_passed_is_ready():
    assert merge_readiness(_evidence(gate("G04_OPERATION_ACCOUNTING", "passed")))["ready"]


def test_a_deferred_gate_outside_the_exemptions_blocks():
    """Otherwise any gate could be excused by writing a reason into it."""
    readiness = merge_readiness(_evidence(gate("G12_EXECUTION_RECEIPTS", "deferred")))
    assert not readiness["ready"]
    assert readiness["blocking_gates"][0]["gate_id"] == "G12_EXECUTION_RECEIPTS"


def test_a_merge_time_verified_gate_may_be_deferred():
    assert merge_readiness(_evidence(gate("G23_NO_MERGE", "deferred")))["ready"]


def test_an_out_of_scope_gate_may_be_deferred_only_when_declared():
    evidence = _evidence(gate("G17_6_OF_6_PRODUCER_EXPORTS", "deferred"))
    assert not merge_readiness(evidence)["ready"]
    assert merge_readiness(evidence, HUB_SLICE_OUT_OF_SCOPE)["ready"]


def test_a_failed_gate_blocks_even_when_declared_out_of_scope():
    """Out of scope excuses absence, never a refutation."""
    evidence = _evidence(gate("G17_6_OF_6_PRODUCER_EXPORTS", "failed"))
    assert not merge_readiness(evidence, HUB_SLICE_OUT_OF_SCOPE)["ready"]


def test_a_blocked_gate_always_blocks():
    evidence = _evidence(gate("G07_NATIVE_SECRETS", "blocked_not_certified"))
    assert not merge_readiness(evidence, HUB_SLICE_OUT_OF_SCOPE)["ready"]


def test_exemptions_are_enumerated_not_open_ended():
    """If this set grows, it should be a visible diff, not an emergent property."""
    assert MERGE_TIME_VERIFIED == {
        "G01_BASELINE_PINNED",
        "G02_PR94_UNCHANGED",
        "G23_NO_MERGE",
    }
    assert set(HUB_SLICE_OUT_OF_SCOPE) == {
        "G09_REPOSITORY_ACQUISITION",
        "G17_6_OF_6_PRODUCER_EXPORTS",
    }


def test_readiness_publishes_what_it_excused():
    readiness = merge_readiness(_evidence(gate("G23_NO_MERGE", "deferred")), HUB_SLICE_OUT_OF_SCOPE)
    assert set(readiness["out_of_scope"]) == set(HUB_SLICE_OUT_OF_SCOPE)
    assert readiness["merge_time_verified"] == sorted(MERGE_TIME_VERIFIED)


# ── the checks behind the attestations ──────────────────────────────────────


def test_every_enabled_operation_has_a_built_rollback_strategy():
    """The finding that made G13 closable at Hub scope, pinned so it stays true."""
    result = check_enabled_rollback_coverage()
    assert result["strategies_uncovered"] == []
    assert result["enabled_operations"] == 12
    assert result["satisfied"]


def test_the_rollback_check_notices_an_unbuilt_strategy(tmp_path):
    """Guard the guard: a check only observed to pass proves nothing."""
    policy = tmp_path / "policy.json"
    policy.write_text(
        json.dumps(
            {
                "policy": {
                    "operations": [
                        {
                            "operation_id": "x.y",
                            "enablement": "ENABLED",
                            "rollback_strategy": "not_a_real_strategy",
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    result = check_enabled_rollback_coverage(policy)
    assert result["strategies_uncovered"] == ["not_a_real_strategy"]
    assert not result["satisfied"]


def test_no_enabled_operation_carries_a_deletion_category():
    assert check_no_deletion_capability()["satisfied"]


def test_the_unbuilt_strategies_are_declared_only_by_disabled_operations():
    """Records the real count, which an earlier evidence file put at three.

    Five distinct identifiers are declared but not implemented. A sixth value
    was prose rather than an identifier; normalising it collapsed it into
    ``delete_staging_download``, which was already among the five. Every one of
    them belongs to an operation that cannot run, so none affects the enabled
    plane -- but they are a real gap in the vector and are counted as such.
    """
    built = implemented_rollback_strategies() | {"none"}
    unbuilt = {
        op["rollback_strategy"]
        for op in POLICY
        if op["rollback_strategy"] not in built
    }
    assert unbuilt == {
        "delete_staging_download",
        "dispatch_receipt_compensating_remove",
        "queue_run_partition_delete",
        "transaction_snapshot_and_run_partition_restore",
        "transactional_run_partition_restore",
    }
    assert all(
        op["enablement"] != "ENABLED" for op in POLICY if op["rollback_strategy"] in unbuilt
    )


# ── policy builder hardening ────────────────────────────────────────────────


def test_every_strategy_the_policy_names_is_either_built_or_declared_unbuilt():
    """No third category. A value in neither registry would fail only at run time.

    ``require_strategy`` raises on an unknown name, so a policy row naming
    something absent from both sets would turn into a runtime error the moment
    that operation was enabled -- long after the policy was signed and reviewed.
    """
    from server.backend.federation_manager_transactions import (
        STRATEGIES,
        UNIMPLEMENTED_STRATEGIES,
    )

    known = set(STRATEGIES) | set(UNIMPLEMENTED_STRATEGIES) | {"none"}
    referenced = {op["rollback_strategy"] for op in POLICY}
    assert referenced <= known, referenced - known


def test_no_strategy_is_both_built_and_declared_unbuilt():
    from server.backend.federation_manager_transactions import (
        STRATEGIES,
        UNIMPLEMENTED_STRATEGIES,
    )

    assert not (set(STRATEGIES) & set(UNIMPLEMENTED_STRATEGIES))


def test_prose_is_not_a_rollback_strategy():
    with pytest.raises(ValueError):
        validate_rollback_strategy("hub.fetch", "delete staging checkout; preserve prior pointer")


def test_a_known_identifier_is_accepted():
    assert validate_rollback_strategy("hub.ingest", "file_snapshot_restore")


def test_the_shipped_policy_carries_only_known_identifiers():
    """The defect this guard exists for: one row shipped carrying prose."""
    for operation in POLICY:
        assert operation["rollback_strategy"] in KNOWN_ROLLBACK_STRATEGIES, operation[
            "operation_id"
        ]
