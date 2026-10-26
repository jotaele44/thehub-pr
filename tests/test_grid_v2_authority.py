"""Regression tests for PR Grid V2 authority commit verification."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from hub.grid_v2 import AUTHORITY_COMMIT, GridV2PinError
from hub.grid_v2_authority import validate_authority_commit_object


def _fake_git(*, head: str, commit_exists: bool = True):
    def fake_run(args, **kwargs):
        if "cat-file" in args:
            if not commit_exists:
                raise subprocess.CalledProcessError(128, args)
            return SimpleNamespace(stdout="")
        if "rev-parse" in args:
            return SimpleNamespace(stdout=head + "\n")
        raise AssertionError(f"unexpected git command: {args}")

    return fake_run


def test_pinned_authority_commit_object_passes_with_moving_head(
    monkeypatch,
    tmp_path: Path,
):
    newer_head = "f" * 40
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_git(head=newer_head),
    )
    assert validate_authority_commit_object(tmp_path) == newer_head


def test_exact_authority_head_passes_in_strict_mode(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_git(head=AUTHORITY_COMMIT),
    )
    assert (
        validate_authority_commit_object(tmp_path, require_head=True)
        == AUTHORITY_COMMIT
    )


def test_wrong_authority_head_fails_closed_only_in_strict_mode(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_git(head="f" * 40),
    )
    with pytest.raises(GridV2PinError, match="authority HEAD mismatch"):
        validate_authority_commit_object(tmp_path, require_head=True)


def test_missing_pinned_git_authority_commit_is_blocked(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_git(head=AUTHORITY_COMMIT, commit_exists=False),
    )
    with pytest.raises(GridV2PinError, match="commit verification BLOCKED"):
        validate_authority_commit_object(tmp_path)
