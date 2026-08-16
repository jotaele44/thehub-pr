from __future__ import annotations

import pytest

from fed_entry import RemoteIdentityError, _requires_remote_identity, validate_remote_identity_rows


REPOSITORIES = [
    {"repo": "jotaele44/skywatcher-pr", "repo_id": 890197690},
    {"repo": "jotaele44/thehub-pr", "repo_id": 1172818213},
]


def test_remote_or_applied_run_requires_stable_identity_gate():
    assert _requires_remote_identity(["snapshot", "--remote"]) is True
    assert _requires_remote_identity(["max", "--apply"]) is True
    assert _requires_remote_identity(["pickup"]) is False


def test_exact_remote_repository_ids_pass():
    validate_remote_identity_rows(
        REPOSITORIES,
        {
            "jotaele44/skywatcher-pr": 890197690,
            "jotaele44/thehub-pr": 1172818213,
        },
    )


def test_remote_repository_id_mismatch_fails_closed():
    with pytest.raises(RemoteIdentityError, match="remote_repository_id_mismatch"):
        validate_remote_identity_rows(
            REPOSITORIES,
            {
                "jotaele44/skywatcher-pr": 1,
                "jotaele44/thehub-pr": 1172818213,
            },
        )


def test_remote_repository_universe_mismatch_fails_closed():
    with pytest.raises(RemoteIdentityError, match="remote_identity_universe_mismatch"):
        validate_remote_identity_rows(
            REPOSITORIES,
            {"jotaele44/thehub-pr": 1172818213},
        )
