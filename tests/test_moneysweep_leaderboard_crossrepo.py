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


def test_current_money_sweep_release_and_receipt_fail_closed_together():
    root = _producer_root()
    release_path = root / "data" / "manifests" / "leaderboards" / "leaderboard_release_contract_v1.json"
    receipt_path = root / "data" / "manifests" / "leaderboards" / "MONEYSWEEP_LEADERBOARD_CERTIFICATION.json"
    _require_or_skip(release_path)
    _require_or_skip(receipt_path)
    release = json.loads(release_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert release["ranking_contract"] == consumer.EXPECTED_RANKING
    assert release["ontology_contract"] == consumer.EXPECTED_ONTOLOGY
    assert receipt["rankingContractVersion"] == consumer.EXPECTED_RANKING
    assert receipt["ontologyContractVersion"] == consumer.EXPECTED_ONTOLOGY

    if release.get("certification_state") != "PASS" or receipt.get("state") != "PASS":
        assert release.get("promotion_authorized") is False
        assert receipt.get("promotionAuthorized") is False
        assert receipt.get("certificationIssued") is False
        assert receipt.get("zeroMaterialUnresolvedResidue") is False


def test_strict_crossrepo_mode_requires_all_producer_contract_files():
    if os.environ.get("PRII_REQUIRE_MONEYSWEEP_LEADERBOARD_CONTRACT") != "1":
        pytest.skip("strict cross-repository release mode not enabled")
    root = _producer_root()
    required = [
        root / "schemas" / "leaderboard_export_package.schema.json",
        root / "data" / "manifests" / "leaderboards" / "leaderboard_release_contract_v1.json",
        root / "data" / "manifests" / "leaderboards" / "MONEYSWEEP_LEADERBOARD_CERTIFICATION.json",
    ]
    missing = [str(path) for path in required if not path.exists()]
    assert not missing, f"missing required MoneySweep leaderboard producer contract files: {missing}"
