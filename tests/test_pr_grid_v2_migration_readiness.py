"""Regression gates for PR Grid V2 domain migration readiness."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_pr_grid_v2_migration_readiness import (  # noqa: E402
    ReadinessError,
    validate_ledger,
)

LEDGER = ROOT / "federation/spatial/pr_grid_v2_migration_readiness.json"

EXPECTED_STATES = {
    "aguayluz-pr": "PASS",
    "skywatcher-pr": "BLOCKED",
    "ovnis-pr": "BLOCKED",
    "moneysweep-pr": "BLOCKED",
    "centinelas-pr": "BLOCKED",
}


def _payload() -> dict:
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def _by_repo(payload: dict) -> dict[str, dict]:
    return {row["repository"]: row for row in payload["domain_denominator"]}


def test_current_migration_readiness_denominator_is_exact():
    payload = _payload()
    validate_ledger(payload)
    states = {
        row["repository"]: row["readiness_state"]
        for row in payload["domain_denominator"]
    }
    assert states == EXPECTED_STATES


def test_only_aguayluz_can_enter_exact_production_profiles():
    payload = _payload()
    by_repo = _by_repo(payload)

    assert by_repo["aguayluz-pr"]["exact_binding_permitted"] is True
    assert by_repo["aguayluz-pr"]["production_profile_permitted"] is True
    assert by_repo["aguayluz-pr"]["migration_class"] == (
        "RECOMPUTED_FROM_SOURCE_COORDINATE"
    )

    for repo in EXPECTED_STATES.keys() - {"aguayluz-pr"}:
        assert by_repo[repo]["exact_binding_permitted"] is False
        assert by_repo[repo]["production_profile_permitted"] is False
        assert by_repo[repo]["migration_class"] is None
        assert by_repo[repo]["blocker_codes"]


def test_wrong_grid_manifest_hash_fails_closed():
    payload = _payload()
    payload["grid_identity"]["Grid_Manifest_SHA256"] = "0" * 64
    with pytest.raises(ReadinessError, match="grid_identity"):
        validate_ledger(payload)


def test_blocked_domain_cannot_silently_enable_exact_binding():
    payload = _payload()
    by_repo = _by_repo(payload)
    by_repo["skywatcher-pr"]["exact_binding_permitted"] = True
    with pytest.raises(ReadinessError, match="BLOCKED cannot permit exact binding"):
        validate_ledger(payload)


def test_pass_source_cannot_be_fixture_sample_or_conformance_artifact():
    payload = _payload()
    by_repo = _by_repo(payload)
    source = next(
        row
        for row in by_repo["aguayluz-pr"]["evidence"]
        if row["role"] == "SOURCE"
    )
    source["path"] = "tests/fixtures/fake-production-source.jsonl"
    with pytest.raises(ReadinessError, match="production SOURCE cannot use"):
        validate_ledger(payload)


def test_all_production_source_roles_are_frozen_and_nonfixture():
    payload = _payload()
    forbidden = ("tests/", "fixtures/", "samples/", "conformance/")
    for domain in payload["domain_denominator"]:
        for evidence in domain["evidence"]:
            if evidence["role"] != "SOURCE":
                continue
            path = evidence["path"].lower()
            assert not any(marker in path for marker in forbidden)
            assert len(evidence["frozen_commit"]) == 40
            assert len(evidence["git_blob_sha1"]) == 40


def test_thehub_never_becomes_geometry_authority():
    payload = _payload()
    assert payload["control_plane"]["repository"] == "thehub-pr"
    assert payload["control_plane"]["geometry_authority"] is False
    assert payload["control_plane"]["role"] == (
        "VALIDATE_AND_AGGREGATE_REFERENCE_ONLY"
    )

    mutated = copy.deepcopy(payload)
    mutated["control_plane"]["geometry_authority"] = True
    with pytest.raises(ReadinessError, match="cannot become geometry authority"):
        validate_ledger(mutated)


def test_pass_requires_real_frozen_source_evidence():
    payload = _payload()
    by_repo = _by_repo(payload)
    by_repo["aguayluz-pr"]["evidence"] = [
        row
        for row in by_repo["aguayluz-pr"]["evidence"]
        if row["role"] != "SOURCE"
    ]
    with pytest.raises(ReadinessError, match="PASS requires frozen SOURCE evidence"):
        validate_ledger(payload)


def test_pass_denominator_cannot_expand_without_evidence_adjudication():
    payload = _payload()
    by_repo = _by_repo(payload)
    row = by_repo["ovnis-pr"]
    row["readiness_state"] = "PASS"
    row["exact_binding_permitted"] = True
    row["production_profile_permitted"] = True
    row["migration_class"] = "RECOMPUTED_FROM_SOURCE_COORDINATE"
    row["blocker_codes"] = []
    row["evidence"] = [
        {
            "role": "SOURCE",
            "repository": "jotaele44/ovnis-pr",
            "path": "releases/2026-06-23/ovnis_cases_master.csv",
            "frozen_commit": "1" * 40,
            "git_blob_sha1": "8b97115f32bfbe48e80fd96a36d74e4e4e168226",
        }
    ]
    payload["control_plane"]["current_pass_domains"] = [
        "aguayluz-pr",
        "ovnis-pr",
    ]
    payload["control_plane"]["current_blocked_domains"] = [
        "centinelas-pr",
        "moneysweep-pr",
        "skywatcher-pr",
    ]

    with pytest.raises(ReadinessError, match="PASS denominator changed"):
        validate_ledger(payload)
