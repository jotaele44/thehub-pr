from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from server.backend import moneysweep_leaderboards as consumer


def _producer_root() -> Path:
    configured = os.environ.get("PRII_MONEYSWEEP_REPO", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path(__file__).resolve().parents[2] / "moneysweep-pr").resolve()


def _require_or_skip(path: Path) -> None:
    if path.exists():
        return
    if os.environ.get("PRII_REQUIRE_MONEYSWEEP_LEADERBOARD_CONTRACT") == "1":
        pytest.fail(f"required MoneySweep leaderboard producer contract missing: {path}")
    pytest.skip(f"MoneySweep leaderboard producer branch not mounted: {path}")


def test_consumer_contract_matches_money_sweep_export_schema():
    root = _producer_root()
    schema_path = root / "schemas" / "leaderboard_export_package.schema.json"
    _require_or_skip(schema_path)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    properties = schema["properties"]
    assert properties["schemaVersion"]["const"] == consumer.EXPECTED_SCHEMA
    assert properties["producer"]["const"] == "moneysweep-pr"
    assert properties["rankingContractVersion"]["const"] == consumer.EXPECTED_RANKING
    assert properties["ontologyContractVersion"]["const"] == consumer.EXPECTED_ONTOLOGY
    assert properties["certification"]["properties"]["state"]["const"] == "PASS"


def test_current_money_sweep_release_cannot_be_promoted_while_blocked():
    root = _producer_root()
    release_path = root / "data" / "manifests" / "leaderboards" / "leaderboard_release_contract_v1.json"
    _require_or_skip(release_path)
    release = json.loads(release_path.read_text(encoding="utf-8"))
    # This assertion is intentionally state-sensitive during the pre-certification
    # phase. Once MoneySweep reaches PASS, replace it with an exact certified
    # package replay test in the same PR that changes the release state.
    if release.get("certification_state") != "PASS":
        assert release.get("promotion_authorized") is False
