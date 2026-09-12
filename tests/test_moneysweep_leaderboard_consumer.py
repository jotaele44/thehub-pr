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
        "generatedAt": "2026-09-12T00:00:00+00:00",
        "certification": {
            "state": "PASS",
            "receiptSha256": "b" * 64,
            "releaseManifestSha256": "c" * 64,
        },
        "categories": [
            {
                "categoryId": "contract_award",
                "metricType": "AWARDED",
                "snapshotId": "snapshot-1",
                "snapshotSha256": "d" * 64,
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


def test_missing_package_fails_closed(tmp_path: Path):
    with pytest.raises(HTTPException) as exc:
        consumer._load_package(tmp_path / "missing.json")
    assert exc.value.status_code == 409
    assert exc.value.detail["state"] == "BLOCKED"


def test_untrusted_receipt_and_release_fail_closed(tmp_path: Path, monkeypatch):
    path = tmp_path / "leaderboard_package.json"
    path.write_text(json.dumps(_package()), encoding="utf-8")
    monkeypatch.delenv("PRII_MONEYSWEEP_LEADERBOARD_RECEIPT_SHA256", raising=False)
    monkeypatch.delenv("PRII_MONEYSWEEP_LEADERBOARD_RELEASE_SHA256", raising=False)
    with pytest.raises(HTTPException) as exc:
        consumer._load_package(path)
    assert exc.value.detail["state"] == "BLOCKED"
    assert exc.value.detail["receiptTrusted"] is False
    assert exc.value.detail["releaseTrusted"] is False


def test_trusted_package_preserves_producer_rows(tmp_path: Path, monkeypatch):
    path = tmp_path / "leaderboard_package.json"
    package = _package()
    path.write_text(json.dumps(package), encoding="utf-8")
    monkeypatch.setenv("PRII_MONEYSWEEP_LEADERBOARD_RECEIPT_SHA256", "b" * 64)
    monkeypatch.setenv("PRII_MONEYSWEEP_LEADERBOARD_RELEASE_SHA256", "c" * 64)
    loaded = consumer._load_package(path)
    assert loaded["categories"][0]["rows"] == package["categories"][0]["rows"]
    assert loaded["consumerPackageSha256"]


def test_name_only_identity_is_rejected():
    package = _package()
    package["categories"][0]["rows"][0]["entityResolutionState"] = "NAME_ONLY"
    assert "categories.contract_award.nameOnlyIdentity" in consumer._validate_package(package)


def test_duplicate_entity_currency_pair_is_rejected():
    package = _package()
    duplicate = dict(package["categories"][0]["rows"][0])
    duplicate["rank"] = 3
    duplicate["metricValue"] = 80.0
    package["categories"][0]["rows"].append(duplicate)
    assert "categories.contract_award.entityUniqueness" in consumer._validate_package(package)


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
    assert "categories.contract_award.competitionRank" in consumer._validate_package(package)


def test_blank_currency_and_snapshot_hash_are_rejected():
    package = _package()
    package["categories"][0]["snapshotSha256"] = ""
    package["categories"][0]["rows"][0]["currency"] = ""
    errors = consumer._validate_package(package)
    assert "categories.contract_award.snapshotSha256" in errors
    assert "categories.contract_award.currency" in errors


def test_empty_category_set_is_rejected():
    package = _package()
    package["categories"] = []
    assert "categories" in consumer._validate_package(package)
