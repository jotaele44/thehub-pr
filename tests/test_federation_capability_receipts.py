from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "reconcile_remote_receipts",
    Path("scripts/federation_reconcile_remote_receipts.py"),
)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(mod)

META = {
    "schema_version": "spiderweb.jp-flood-live-receipt/v1",
    "source_main_sha": "fcc340585c851b9bb568a38098c2c9585c83c7f3",
    "workflow_run_id": 35688020606,
    "transition_status": "PASS",
    "transition_listed_count": 77,
    "transition_count": 0,
    "reproducibility_status": "PASS",
    "blocking_count": 0,
    "identical_count": 78,
    "metadata_only_count": 0,
    "certification_invariant": "live observations never auto-promote frozen source_state",
}

RECEIPT = {
    "schema_version": "spiderweb.jp-flood-live-receipt/v1",
    "source_main_sha": "fcc340585c851b9bb568a38098c2c9585c83c7f3",
    "workflow_run_id": 35688020606,
    "certification_invariant": "live observations never auto-promote frozen source_state",
    "transition": {
        "status": "PASS",
        "listed_count": 77,
        "transition_count": 0,
    },
    "reproducibility": {
        "status": "PASS",
        "blocking_count": 0,
        "identical_count": 78,
        "metadata_only_count": 0,
    },
}


def test_jp_flood_capability_receipt_passes() -> None:
    assert mod.validate_capability_receipt(
        "jp-flood-certification", META, RECEIPT
    ) == []


def test_source_main_sha_drift_fails() -> None:
    receipt = copy.deepcopy(RECEIPT)
    receipt["source_main_sha"] = "0" * 40
    errors = mod.validate_capability_receipt(
        "jp-flood-certification", META, receipt
    )
    assert any("source_main_sha mismatch" in error for error in errors)


def test_transition_drift_fails() -> None:
    receipt = copy.deepcopy(RECEIPT)
    receipt["transition"]["status"] = "REQUIRES_READJUDICATION"
    receipt["transition"]["transition_count"] = 1
    errors = mod.validate_capability_receipt(
        "jp-flood-certification", META, receipt
    )
    assert any("transition.status mismatch" in error for error in errors)
    assert any("transition.transition_count mismatch" in error for error in errors)


def test_reproducibility_byte_drift_fails() -> None:
    receipt = copy.deepcopy(RECEIPT)
    receipt["reproducibility"]["status"] = "REQUIRES_READJUDICATION"
    receipt["reproducibility"]["blocking_count"] = 1
    receipt["reproducibility"]["identical_count"] = 77
    errors = mod.validate_capability_receipt(
        "jp-flood-certification", META, receipt
    )
    assert any("reproducibility.status mismatch" in error for error in errors)
    assert any("reproducibility.blocking_count mismatch" in error for error in errors)
    assert any("reproducibility.identical_count mismatch" in error for error in errors)


def test_certification_invariant_drift_fails() -> None:
    receipt = copy.deepcopy(RECEIPT)
    receipt["certification_invariant"] = "live observations may auto-promote"
    errors = mod.validate_capability_receipt(
        "jp-flood-certification", META, receipt
    )
    assert any("certification_invariant mismatch" in error for error in errors)
