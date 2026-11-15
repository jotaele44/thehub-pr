"""Regression tests for exact PR Grid V2 authority commit verification."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from hub.grid_v2 import AUTHORITY_COMMIT, GridV2PinError
from hub.grid_v2_authority import validate_authority_commit_object


def test_exact_authority_commit_object_passes(monkeypatch, tmp_path: Path):
    def fake_run(*args, **kwargs):
        return SimpleNamespace(stdout=AUTHORITY_COMMIT + "\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert validate_authority_commit_object(tmp_path) == AUTHORITY_COMMIT


def test_wrong_authority_commit_object_fails_closed(monkeypatch, tmp_path: Path):
    def fake_run(*args, **kwargs):
        return SimpleNamespace(stdout="f" * 40 + "\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(GridV2PinError, match="authority commit mismatch"):
        validate_authority_commit_object(tmp_path)


def test_missing_git_authority_commit_is_blocked(monkeypatch, tmp_path: Path):
    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(128, ["git", "rev-parse", "HEAD"])

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(GridV2PinError, match="commit verification BLOCKED"):
        validate_authority_commit_object(tmp_path)
