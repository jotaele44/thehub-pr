from __future__ import annotations

import pytest

from fed_entry import (
    RemoteIdentityError,
    _post_execution_repository_status,
    _requires_remote_identity,
    validate_remote_identity_rows,
)


REPOSITORIES = [
    {"repo": "jotaele44/skywatcher-pr", "repo_id": 1261399537},
    {"repo": "jotaele44/thehub-pr", "repo_id": 1258897469},
]


def test_remote_or_applied_run_requires_stable_identity_gate():
    assert _requires_remote_identity(["snapshot", "--remote"]) is True
    assert _requires_remote_identity(["max", "--apply"]) is True
    assert _requires_remote_identity(["pickup"]) is False


def test_exact_remote_repository_ids_pass():
    validate_remote_identity_rows(
        REPOSITORIES,
        {
            "jotaele44/skywatcher-pr": 1261399537,
            "jotaele44/thehub-pr": 1258897469,
        },
    )


def test_remote_repository_id_mismatch_fails_closed():
    with pytest.raises(RemoteIdentityError, match="remote_repository_id_mismatch"):
        validate_remote_identity_rows(
            REPOSITORIES,
            {
                "jotaele44/skywatcher-pr": 1,
                "jotaele44/thehub-pr": 1258897469,
            },
        )


def test_remote_repository_universe_mismatch_fails_closed():
    with pytest.raises(RemoteIdentityError, match="remote_identity_universe_mismatch"):
        validate_remote_identity_rows(
            REPOSITORIES,
            {"jotaele44/thehub-pr": 1258897469},
        )


def test_post_execution_repository_rollup_uses_final_vector_states():
    ledger = {
        "snapshot": {
            "repositories": [
                {"repo": "jotaele44/thehub-pr"},
                {"repo": "jotaele44/skywatcher-pr"},
            ]
        },
        "vectors": [
            {"vector_id": "CONTROL", "repo": "jotaele44/thehub-pr"},
            {"vector_id": "DESIGN", "repo": "jotaele44/thehub-pr"},
            {"vector_id": "AIR", "repo": "jotaele44/skywatcher-pr"},
        ],
    }
    result = _post_execution_repository_status(
        ledger,
        {"CONTROL": "PASS", "DESIGN": "OPEN", "AIR": "BLOCKED"},
    )
    assert result["phase"] == "post_execution"
    assert result["arithmetic_ok"] is True
    assert result["counts"] == {
        "BLOCKED": 1,
        "FAIL": 0,
        "OPEN": 1,
        "PASS": 0,
        "READY": 0,
        "UNRESOLVED": 0,
    }
    by_repo = {row["repo"]: row["status"] for row in result["repositories"]}
    assert by_repo == {
        "jotaele44/skywatcher-pr": "BLOCKED",
        "jotaele44/thehub-pr": "OPEN",
    }


def test_post_execution_vector_universe_mismatch_fails_closed():
    ledger = {
        "snapshot": {"repositories": [{"repo": "jotaele44/thehub-pr"}]},
        "vectors": [{"vector_id": "CONTROL", "repo": "jotaele44/thehub-pr"}],
    }
    with pytest.raises(RemoteIdentityError, match="post_execution_vector_universe_mismatch"):
        _post_execution_repository_status(ledger, {})
