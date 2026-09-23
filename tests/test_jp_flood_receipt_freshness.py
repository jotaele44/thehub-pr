from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "jp_flood_receipt_freshness",
    Path("scripts/check_jp_flood_receipt_freshness.py"),
)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(mod)

META = {
    "schema_version": "spiderweb.jp-flood-live-receipt/v1",
    "source_main_sha": "fcc340585c851b9bb568a38098c2c9585c83c7f3",
    "workflow_run_id": 35688020606,
    "transition_listed_count": 77,
    "transition_count": 0,
    "blocking_count": 0,
    "identical_count": 78,
    "metadata_only_count": 0,
    "certification_invariant": "live observations never auto-promote frozen source_state",
}

LATEST = {
    "schema_version": "spiderweb.jp-flood-live-receipt/v1",
    "source_main_sha": "fcc340585c851b9bb568a38098c2c9585c83c7f3",
    "workflow_run_id": 35688020606,
    "certification_invariant": "live observations never auto-promote frozen source_state",
    "transition": {"status": "PASS", "listed_count": 77, "transition_count": 0},
    "reproducibility": {
        "status": "PASS",
        "blocking_count": 0,
        "identical_count": 78,
        "metadata_only_count": 0,
    },
}


def test_current_equivalent_passes() -> None:
    result = mod.classify(META, LATEST)
    assert result["status"] == "CURRENT_EQUIVALENT"
    assert result["blocking"] is False


def test_newer_equivalent_same_source_main_passes() -> None:
    latest = copy.deepcopy(LATEST)
    latest["workflow_run_id"] += 1
    result = mod.classify(META, latest)
    assert result["status"] == "CURRENT_EQUIVALENT"
    assert result["blocking"] is False


def test_newer_source_main_requires_deliberate_pin_update() -> None:
    latest = copy.deepcopy(LATEST)
    latest["workflow_run_id"] += 1
    latest["source_main_sha"] = "1" * 40
    result = mod.classify(META, latest)
    assert result["status"] == "PIN_UPDATE_REQUIRED"
    assert result["blocking"] is True


def test_source_state_transition_requires_readjudication() -> None:
    latest = copy.deepcopy(LATEST)
    latest["transition"]["transition_count"] = 1
    result = mod.classify(META, latest)
    assert result["status"] == "REQUIRES_READJUDICATION"
    assert result["blocking"] is True


def test_reproducibility_drift_requires_readjudication() -> None:
    latest = copy.deepcopy(LATEST)
    latest["reproducibility"]["identical_count"] = 77
    latest["reproducibility"]["metadata_only_count"] = 1
    result = mod.classify(META, latest)
    assert result["status"] == "REQUIRES_READJUDICATION"
    assert result["blocking"] is True


def test_explicit_readjudication_flag_blocks() -> None:
    latest = copy.deepcopy(LATEST)
    latest["requires_readjudication"] = True
    result = mod.classify(META, latest)
    assert result["status"] == "REQUIRES_READJUDICATION"
    assert result["blocking"] is True


def test_transport_blocked_is_explicit_but_nonnegative() -> None:
    latest = copy.deepcopy(LATEST)
    latest["transition"]["status"] = "TRANSPORT_BLOCKED"
    result = mod.classify(META, latest)
    assert result["status"] == "TRANSPORT_BLOCKED"
    assert result["blocking"] is False


def test_workflow_run_regression_fails_closed() -> None:
    latest = copy.deepcopy(LATEST)
    latest["workflow_run_id"] -= 1
    try:
        mod.classify(META, latest)
    except mod.FreshnessError as exc:
        assert "workflow_run_id regressed" in str(exc)
    else:
        raise AssertionError("expected FreshnessError")
