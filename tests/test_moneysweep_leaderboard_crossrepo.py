from __future__ import annotations

import hashlib
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_consumer_contract_matches_money_sweep_export_schema_and_scope():
    root = _producer_root()
    schema_path = root / "schemas" / "leaderboard_export_package.schema.json"
    scope_path = root / "data" / "manifests" / "leaderboards" / "leaderboard_certification_scope_v1.json"
    _require_or_skip(schema_path)
    _require_or_skip(scope_path)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    scope = json.loads(scope_path.read_text(encoding="utf-8"))
    properties = schema["properties"]
    assert properties["schemaVersion"]["const"] == consumer.EXPECTED_SCHEMA
    assert properties["producer"]["const"] == "moneysweep-pr"
    assert properties["rankingContractVersion"]["const"] == consumer.EXPECTED_RANKING
    assert properties["ontologyContractVersion"]["const"] == consumer.EXPECTED_ONTOLOGY
    assert properties["scopeId"]["const"] == consumer.EXPECTED_SCOPE
    assert properties["categories"]["items"]["properties"]["categoryId"]["const"] == consumer.EXPECTED_CATEGORY
    assert properties["categories"]["items"]["properties"]["metricType"]["const"] == consumer.EXPECTED_METRIC
    assert properties["certification"]["properties"]["state"]["const"] == "PASS"
    assert "scopeSha256" in properties["certification"]["required"]
    assert "certificationRuntimeSha256" in properties["certification"]["required"]
    assert "certificationRuntimeManifest" in schema["required"]
    assert properties["certificationRuntimeManifest"]["properties"]["schemaVersion"]["const"] == consumer.EXPECTED_CERT_RUNTIME
    category_required = properties["categories"]["items"]["required"]
    for field in ("accounting", "sourceVersion", "sourceManifestations", "runtimeManifest", "snapshotCertification"):
        assert field in category_required
    assert scope["scopeId"] == consumer.EXPECTED_SCOPE
    assert [item["categoryId"] for item in scope["includedCategories"]] == [consumer.EXPECTED_CATEGORY]


def test_current_money_sweep_release_and_receipt_fail_closed_together():
    root = _producer_root()
    release_path = root / "data" / "manifests" / "leaderboards" / "leaderboard_release_contract_v1.json"
    receipt_path = root / "data" / "manifests" / "leaderboards" / "MONEYSWEEP_LEADERBOARD_CERTIFICATION.json"
    scope_path = root / "data" / "manifests" / "leaderboards" / "leaderboard_certification_scope_v1.json"
    _require_or_skip(release_path)
    _require_or_skip(receipt_path)
    _require_or_skip(scope_path)
    release = json.loads(release_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    scope = json.loads(scope_path.read_text(encoding="utf-8"))

    assert release["ranking_contract"] == consumer.EXPECTED_RANKING
    assert release["ontology_contract"] == consumer.EXPECTED_ONTOLOGY
    assert release["certification_scope"] == consumer.EXPECTED_SCOPE
    assert receipt["rankingContractVersion"] == consumer.EXPECTED_RANKING
    assert receipt["ontologyContractVersion"] == consumer.EXPECTED_ONTOLOGY
    assert scope["scopeId"] == consumer.EXPECTED_SCOPE
    assert scope["ciExecutionPolicy"]["assertsPass"] is False

    if release.get("certification_state") != "PASS" or receipt.get("state") != "PASS":
        assert release.get("promotion_authorized") is False
        assert receipt.get("promotionAuthorized") is False
        assert receipt.get("certificationIssued") is False
        assert receipt.get("zeroMaterialUnresolvedResidue") is False


def test_exact_producer_package_replay_when_materialized(tmp_path: Path, monkeypatch):
    root = _producer_root()
    package_path = root / "data" / "exports" / "leaderboards" / "leaderboard_package.json"
    receipt_path = root / "data" / "manifests" / "leaderboards" / "MONEYSWEEP_LEADERBOARD_CERTIFICATION.json"
    release_path = root / "data" / "manifests" / "leaderboards" / "leaderboard_release_contract_v1.json"
    scope_path = root / "data" / "manifests" / "leaderboards" / "leaderboard_certification_scope_v1.json"
    for path in (package_path, receipt_path, release_path, scope_path):
        _require_or_skip(path)

    monkeypatch.setenv("PRII_MONEYSWEEP_LEADERBOARD_RECEIPT_SHA256", _sha256(receipt_path))
    monkeypatch.setenv("PRII_MONEYSWEEP_LEADERBOARD_RELEASE_SHA256", _sha256(release_path))
    monkeypatch.setenv("PRII_MONEYSWEEP_LEADERBOARD_SCOPE_SHA256", _sha256(scope_path))
    monkeypatch.setenv("PRII_MONEYSWEEP_LEADERBOARD_PACKAGE_SHA256", _sha256(package_path))
    loaded = consumer._load_package(package_path)
    assert loaded["scopeId"] == consumer.EXPECTED_SCOPE
    assert len(loaded["categories"]) == 1
    category = loaded["categories"][0]
    assert category["categoryId"] == consumer.EXPECTED_CATEGORY
    assert category["metricType"] == consumer.EXPECTED_METRIC
    assert category["rows"]
    assert category["accounting"]["arithmeticClosed"] is True
    assert category["accounting"]["unresolvedRecords"] == 0
    assert category["accounting"]["excludedRecords"] == 0
    assert category["runtimeManifest"]["producerCommit"] == loaded["producerCommit"]
    assert category["snapshotCertification"]["zeroMaterialUnresolvedResidue"] is True
    assert loaded["consumerPackageSha256"] == _sha256(package_path)


def test_strict_crossrepo_mode_requires_all_producer_contract_files():
    if os.environ.get("PRII_REQUIRE_MONEYSWEEP_LEADERBOARD_CONTRACT") != "1":
        pytest.skip("strict cross-repository release mode not enabled")
    root = _producer_root()
    required = [
        root / "schemas" / "leaderboard_export_package.schema.json",
        root / "scripts" / "leaderboard_release_provenance.py",
        root / "data" / "manifests" / "leaderboards" / "leaderboard_release_contract_v1.json",
        root / "data" / "manifests" / "leaderboards" / "MONEYSWEEP_LEADERBOARD_CERTIFICATION.json",
        root / "data" / "manifests" / "leaderboards" / "leaderboard_certification_scope_v1.json",
        root / "data" / "manifests" / "leaderboards" / "debt_history_source_refs_v1.json",
        root / "data" / "exports" / "leaderboards" / "leaderboard_package.json",
    ]
    missing = [str(path) for path in required if not path.exists()]
    assert not missing, f"missing required MoneySweep leaderboard producer contract files: {missing}"
