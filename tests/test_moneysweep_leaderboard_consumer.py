from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from server.backend import moneysweep_leaderboards as consumer


def _package():
    return {
        "schemaVersion": "moneysweep.leaderboard-export-package/v1",
        "producer": "moneysweep-pr",
        "producerCommit": "a" * 40,
        "rankingContractVersion": "moneysweep.leaderboard/v1.1",
        "ontologyContractVersion": "moneysweep.financial-category-ontology/v1.1",
        "scopeId": "moneysweep.leaderboard.production-v1",
        "generatedAt": "2026-09-13T18:00:00+00:00",
        "certification": {
            "state": "PASS",
            "receiptSha256": "b" * 64,
            "releaseManifestSha256": "c" * 64,
            "scopeSha256": "d" * 64,
        },
        "categories": [
            {
                "categoryId": "debt_issuance",
                "metricType": "DEBT_ISSUED_PAR",
                "snapshotId": "snapshot-1",
                "snapshotSha256": "e" * 64,
                "rows": [
                    {
                        "entityId": "entity-1",
                        "entityDisplayName": "Alpha",
                        "metricValue": 100.0,
                        "currency": "USD",
                        "rank": 1,
                        "entityResolutionState": "CANONICAL_V1_ENTITY_ID",
                    },
                    {
                        "entityId": "entity-2",
                        "entityDisplayName": "Beta",
                        "metricValue": 90.0,
                        "currency": "USD",
                        "rank": 2,
                        "entityResolutionState": "CANONICAL_V1_ENTITY_ID",
                    },
                ],
            }
        ],
    }


def _trust(monkeypatch):
    monkeypatch.setenv("PRII_MONEYSWEEP_LEADERBOARD_RECEIPT_SHA256", "b" * 64)
    monkeypatch.setenv("PRII_MONEYSWEEP_LEADERBOARD_RELEASE_SHA256", "c" * 64)
    monkeypatch.setenv("PRII_MONEYSWEEP_LEADERBOARD_SCOPE_SHA256", "d" * 64)


def test_missing_package_fails_closed(tmp_path: Path):
    with pytest.raises(HTTPException) as exc:
        consumer._load_package(tmp_path / "missing.json")
    assert exc.value.status_code == 409
    assert exc.value.detail["state"] == "BLOCKED"


def test_untrusted_receipt_release_and_scope_fail_closed(tmp_path: Path, monkeypatch):
    path = tmp_path / "leaderboard_package.json"
    path.write_text(json.dumps(_package()), encoding="utf-8")
    monkeypatch.delenv("PRII_MONEYSWEEP_LEADERBOARD_RECEIPT_SHA256", raising=False)
    monkeypatch.delenv("PRII_MONEYSWEEP_LEADERBOARD_RELEASE_SHA256", raising=False)
    monkeypatch.delenv("PRII_MONEYSWEEP_LEADERBOARD_SCOPE_SHA256", raising=False)
    with pytest.raises(HTTPException) as exc:
        consumer._load_package(path)
    assert exc.value.detail["state"] == "BLOCKED"
    assert exc.value.detail["receiptTrusted"] is False
    assert exc.value.detail["releaseTrusted"] is False
    assert exc.value.detail["scopeTrusted"] is False


def test_trusted_package_preserves_producer_rows(tmp_path: Path, monkeypatch):
    path = tmp_path / "leaderboard_package.json"
    package = _package()
    path.write_text(json.dumps(package), encoding="utf-8")
    _trust(monkeypatch)
    loaded = consumer._load_package(path)
    assert loaded["categories"][0]["rows"] == package["categories"][0]["rows"]
    assert loaded["scopeId"] == consumer.EXPECTED_SCOPE
    assert loaded["consumerPackageSha256"]


def test_scope_drift_is_rejected():
    package = _package()
    package["scopeId"] = "moneysweep.leaderboard.other"
    assert "scopeId" in consumer._validate_package(package)


def test_category_or_metric_outside_scope_is_rejected():
    package = _package()
    package["categories"][0]["categoryId"] = "contract_award"
    package["categories"][0]["metricType"] = "AWARDED"
    errors = consumer._validate_package(package)
    assert "categories.contract_award.scopeCategory" in errors
    assert "categories.contract_award.metricType" in errors


def test_noncanonical_identity_is_rejected():
    package = _package()
    package["categories"][0]["rows"][0]["entityResolutionState"] = "NAME_ONLY"
    assert "categories.debt_issuance.identityState" in consumer._validate_package(package)


def test_duplicate_entity_currency_pair_is_rejected():
    package = _package()
    duplicate = dict(package["categories"][0]["rows"][0])
    duplicate["rank"] = 3
    duplicate["metricValue"] = 80.0
    package["categories"][0]["rows"].append(duplicate)
    assert "categories.debt_issuance.entityUniqueness" in consumer._validate_package(package)


def test_noncompetition_rank_is_rejected():
    package = _package()
    package["categories"][0]["rows"].insert(1, {
        "entityId": "entity-tie",
        "entityDisplayName": "Tie",
        "metricValue": 100.0,
        "currency": "USD",
        "rank": 2,
        "entityResolutionState": "CANONICAL_V1_ENTITY_ID",
    })
    assert "categories.debt_issuance.competitionRank" in consumer._validate_package(package)


def test_non_usd_and_snapshot_hash_are_rejected():
    package = _package()
    package["categories"][0]["snapshotSha256"] = ""
    package["categories"][0]["rows"][0]["currency"] = "EUR"
    errors = consumer._validate_package(package)
    assert "categories.debt_issuance.snapshotSha256" in errors
    assert "categories.debt_issuance.currency" in errors


def test_empty_or_multi_category_package_is_rejected():
    package = _package()
    package["categories"] = []
    assert "categories.scopeCardinality" in consumer._validate_package(package)

    package = _package()
    package["categories"].append(dict(package["categories"][0]))
    assert "categories.scopeCardinality" in consumer._validate_package(package)
