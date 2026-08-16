from __future__ import annotations

import copy
from pathlib import Path

import pytest

from fed_control import (
    FedError,
    _command_allowed,
    load_ledger,
    reconcile,
    repository_statuses,
    run_max,
    validate_ledger,
)

LEDGER = Path(__file__).resolve().parents[1] / "registry" / "development_vectors.yaml"


def _ledger():
    return load_ledger(LEDGER)


def _exact_snapshot(ledger):
    return {
        "repositories": [
            {
                "repo": row["repo"],
                "repo_id": row["repo_id"],
                "expected_sha": row["expected_sha"],
                "observed_sha": row["expected_sha"],
                "sha_match": True,
                "error": None,
            }
            for row in ledger["snapshot"]["repositories"]
        ]
    }


def test_canonical_ledger_closes_repository_universe_and_vector_ids():
    result = validate_ledger(_ledger())
    assert result["status"] == "PASS"
    assert result["repository_count"] == 7
    assert result["vector_count"] == 8
    assert result["source_binding_count"] == 10


def test_duplicate_issue_declarations_are_one_to_many_manifestations_not_two_vectors():
    ledger = _ledger()
    by_id = {row["vector_id"]: row for row in ledger["vectors"]}

    agua = by_id["VALIDATE_AGUAYLUZ_REAL_DATA_PARTIAL_EXPORT"]
    assert [b["ref"] for b in agua["source_bindings"]] == [
        "jotaele44/aguayluz-pr#10",
        "jotaele44/aguayluz-pr#11",
    ]
    assert agua["binding_adjudication"]["cardinality"] == "1:N"

    ovnis = by_id["CREATE_PRUFON_CASE_SCHEMA_IMPORT_PIPELINE"]
    assert [b["ref"] for b in ovnis["source_bindings"]] == [
        "jotaele44/ovnis-pr#4",
        "jotaele44/ovnis-pr#5",
    ]
    assert ovnis["binding_adjudication"]["cardinality"] == "1:N"


def test_same_github_issue_cannot_bind_to_two_canonical_vectors():
    ledger = _ledger()
    bad = copy.deepcopy(ledger)
    bad["vectors"][0]["source_bindings"].append(
        {
            "kind": "github_issue",
            "ref": "jotaele44/skywatcher-pr#7",
            "binding_basis": "injected_collision",
        }
    )
    with pytest.raises(FedError, match="github_issue_bound_to_multiple_vectors"):
        validate_ledger(bad)


def test_dependency_cycle_fails_closed():
    ledger = _ledger()
    bad = copy.deepcopy(ledger)
    by_id = {row["vector_id"]: row for row in bad["vectors"]}
    by_id["FEDERATION_PICKUP_SYSTEM_LEVEL_3"]["dependencies"] = [
        "FEDERATION_DESIGN_SYSTEM_V1_ROLLOUT"
    ]
    with pytest.raises(FedError, match="dependency_cycle"):
        validate_ledger(bad)


def test_stale_sha_blocks_previously_ready_vector():
    ledger = _ledger()
    snapshot = _exact_snapshot(ledger)
    for row in snapshot["repositories"]:
        if row["repo"] == "jotaele44/thehub-pr":
            row["observed_sha"] = "0" * 40
            row["sha_match"] = False

    rec = reconcile(ledger, snapshot)
    control = next(
        row for row in rec["vectors"]
        if row["vector_id"] == "FEDERATION_PICKUP_SYSTEM_LEVEL_3"
    )
    assert control["effective_status"] == "BLOCKED"
    assert "stale_or_unverified_sha" in control["blockers"]


def test_exact_snapshot_max_exhausts_only_admissible_control_vector():
    ledger = _ledger()
    rec = reconcile(ledger, _exact_snapshot(ledger))
    result = run_max(ledger, rec, Path("/nonexistent"), apply=False)

    assert result["bounded_exhausted"] is True
    assert result["ready_residue"] == []
    assert "FEDERATION_PICKUP_SYSTEM_LEVEL_3" in result["completed"]
    assert result["final_status"]["BUILD_SKYWATCHER_NON_SYNTHETIC_EXPORT"] == "BLOCKED"
    assert result["final_status"]["DISCOVER_CENTINELAS_ACTIVE_VECTOR"] == "UNRESOLVED"
    assert result["final_status"]["VALIDATE_AGUAYLUZ_REAL_DATA_PARTIAL_EXPORT"] == "OPEN"


def test_repository_status_arithmetic_closes_at_seven():
    ledger = _ledger()
    rec = reconcile(ledger, _exact_snapshot(ledger))
    status = repository_statuses(ledger, rec)
    assert status["arithmetic_ok"] is True
    assert status["classified_count"] == status["repository_count"] == 7
    assert sum(status["counts"].values()) == 7


@pytest.mark.parametrize(
    "command",
    [
        "git push --force origin HEAD:main",
        "git push -f origin HEAD",
        "git branch -D main",
        "git push origin --delete feature/x",
        "gh pr merge 123 --merge",
    ],
)
def test_forbidden_mutation_commands_fail_closed(command):
    vector = {
        "vector_id": "TEST",
        "execution": {
            "mutation": "branch_only",
            "commands": [command],
        },
    }
    with pytest.raises(FedError, match="forbidden_command"):
        _command_allowed(vector)


def test_prohibited_vector_cannot_define_command():
    vector = {
        "vector_id": "TEST",
        "execution": {
            "mutation": "prohibited_by_fed_max",
            "commands": ["python -m pytest"],
        },
    }
    with pytest.raises(FedError, match="mutation_prohibited"):
        _command_allowed(vector)
