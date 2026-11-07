"""Fail-closed tests for federation-wide PR grid V2 runtime parity."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_pr_grid_v2_federation as validator  # noqa: E402
from hub.grid_v2 import GridV2PinError  # noqa: E402


def _materialize_runtime_set(tmp_path: Path) -> None:
    payload = validator.CANONICAL_RUNTIME.read_bytes()
    for consumer in sorted(validator.RUNTIME_CONSUMERS):
        path = tmp_path / consumer / validator.RUNTIME_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)


def test_complete_runtime_denominator_is_byte_identical(tmp_path):
    _materialize_runtime_set(tmp_path)
    digest, details = validator._validate_runtime_set(tmp_path)
    assert set(details) == set(validator.RUNTIME_CONSUMERS)
    assert len(details) == 5
    assert {row["runtime_sha256"] for row in details.values()} == {digest}
    assert all(row["bytes"] > 0 for row in details.values())


def test_missing_runtime_fails_closed(tmp_path):
    _materialize_runtime_set(tmp_path)
    missing = tmp_path / "ovnis-pr" / validator.RUNTIME_REL
    missing.unlink()
    with pytest.raises(GridV2PinError, match="missing V2 runtime for ovnis-pr"):
        validator._validate_runtime_set(tmp_path)


def test_runtime_byte_drift_fails_closed(tmp_path):
    _materialize_runtime_set(tmp_path)
    drifted = tmp_path / "skywatcher-pr" / validator.RUNTIME_REL
    drifted.write_bytes(drifted.read_bytes() + b"\n# drift\n")
    with pytest.raises(GridV2PinError, match="V2 runtime drift for skywatcher-pr"):
        validator._validate_runtime_set(tmp_path)
