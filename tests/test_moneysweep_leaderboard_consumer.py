from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from server.backend import moneysweep_leaderboards as consumer


def _package():
    cert_runtime = {
        "schemaVersion": "moneysweep.leaderboard-certification-runtime/v1",
        "state": "FROZEN",
        "files": [
            {"path": "scripts/export_leaderboard_package.py", "bytes": 10, "sha256": "1" * 64},
            {"path": "schemas/leaderboard_export_package.schema.json", "bytes": 20, "sha256": "2" * 64},
        ],
    }
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
            "certificationRuntimeSha256": consumer._canonical_sha256(cert_runtime),
        },
        "certificationRuntimeManifest": cert_runtime,
        "categories": [
            {
                "categoryId": "debt_issuance",
                "metricType": "DEBT_ISSUED_PAR",
                "snapshotId": "snapshot-1",
                "snapshotSha256": "e" * 64,
                "capturedAt": "2026-09-03T16:35:24+00:00",
                "candidateCount": 2,
                "accounting": {
                    "inputRecords": 2,
                    "outOfScopeRecords": 0,
                    "retainedRecords": 2,
                    "excludedRecords": 0,
                    "unresolvedRecords": 0,
                    "inScopeRecords": 2,
                    "arithmeticClosed": True,
                },
                "sourceVersion": {
                    "type": "GIT_COMMIT",
                    "commit": "f" * 40,
                    "committedAt": "2026-09-03T16:35:24+00:00",
                    "economicActivityInference": False,
                },
                "sourceManifestations": [
                    {
                        "path": "data/canonical_v1/debt_instruments.csv",
                        "bytes": 100,
                        "sha256": "3" * 64,
                        "sourceCommit": "f" * 40,
                    }
                ],
                "runtimeManifest": {
                    "state": "FROZEN",
                    "producerCommit": "a" * 40,
                    "files": [
                        {"path": "server/backend/leaderboard_adapters.py", "bytes": 30, "sha256": "4" * 64}
                    ],
                },
                "snapshotCertification": {
                    "state": "PASS",
                    "scopeId": "moneysweep.leaderboard.production-v1",
                    "sourceSnapshotSha256": "5" * 64,
                    "zeroMaterialUnresolvedResidue": True,
                },
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


def _write_package(path: Path, package: dict | None = None) -> dict:
    value = package or _package()
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return value


def _trust(monkeypatch, path: Path):
    monkeypatch.setenv("PRII_MONEYSWEEP_LEADERBOARD_RECEIPT_SHA256", "b" * 64)
    monkeypatch.setenv("PRII_MONEYSWEEP_LEADERBOARD_RELEASE_SHA256", "c" * 64)
    monkeypatch.setenv("PRII_MONEYSWEEP_LEADERBOARD_SCOPE_SHA256", "d" * 64)
    monkeypatch.setenv(
        "PRII_MONEYSWEEP_LEADERBOARD_PACKAGE_SHA256",
        hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def test_missing_package_fails_closed(tmp_path: Path):
    with pytest.raises(HTTPException) as exc:
        consumer._load_package(tmp_path / "missing.json")
    assert exc.value.status_code == 409
    assert exc.value.detail["state"] == "BLOCKED"


def test_untrusted_receipt_release_scope_and_package_fail_closed(tmp_path: Path, monkeypatch):
    path = tmp_path / "leaderboard_package.json"
    _write_package(path)
    for name in (
        "PRII_MONEYSWEEP_LEADERBOARD_RECEIPT_SHA256",
        "PRII_MONEYSWEEP_LEADERBOARD_RELEASE_SHA256",
        "PRII_MONEYSWEEP_LEADERBOARD_SCOPE_SHA256",
        "PRII_MONEYSWEEP_LEADERBOARD_PACKAGE_SHA256",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(HTTPException) as exc:
        consumer._load_package(path)
    assert exc.value.detail["state"] == "BLOCKED"
    assert exc.value.detail["receiptTrusted"] is False
    assert exc.value.detail["releaseTrusted"] is False
    assert exc.value.detail["scopeTrusted"] is False
    assert exc.value.detail["packageTrusted"] is False


def test_trusted_package_preserves_producer_rows(tmp_path: Path, monkeypatch):
    path = tmp_path / "leaderboard_package.json"
    package = _write_package(path)
    _trust(monkeypatch, path)
    loaded = consumer._load_package(path)
    assert loaded["categories"][0]["rows"] == package["categories"][0]["rows"]
    assert loaded["scopeId"] == consumer.EXPECTED_SCOPE
    assert loaded["consumerPackageSha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_exact_package_hash_detects_post_trust_tampering(tmp_path: Path, monkeypatch):
    path = tmp_path / "leaderboard_package.json"
    package = _write_package(path)
    _trust(monkeypatch, path)
    package["categories"][0]["rows"][0]["metricValue"] = 101.0
    _write_package(path, package)
    with pytest.raises(HTTPException) as exc:
        consumer._load_package(path)
    assert exc.value.detail["state"] == "BLOCKED"
    assert exc.value.detail["packageTrusted"] is False


def test_certification_runtime_hash_tampering_is_rejected():
    package = _package()
    package["certificationRuntimeManifest"]["files"][0]["bytes"] += 1
    assert "certificationRuntimeManifest.sha256" in consumer._validate_package(package)


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


def test_source_commit_and_runtime_commit_drift_are_rejected():
    package = _package()
    package["categories"][0]["sourceManifestations"][0]["sourceCommit"] = "9" * 40
    package["categories"][0]["runtimeManifest"]["producerCommit"] = "8" * 40
    errors = consumer._validate_package(package)
    assert "categories.debt_issuance.sourceCommitMismatch" in errors
    assert "categories.debt_issuance.runtimeProducerCommit" in errors


def test_residue_and_candidate_count_drift_are_rejected():
    package = _package()
    category = package["categories"][0]
    category["accounting"]["unresolvedRecords"] = 1
    category["candidateCount"] = 99
    errors = consumer._validate_package(package)
    assert "categories.debt_issuance.unresolvedRecords" in errors
    assert "categories.debt_issuance.candidateCount" in errors


def test_duplicate_entity_currency_pair_is_rejected():
    package = _package()
    duplicate = dict(package["categories"][0]["rows"][0])
    duplicate["rank"] = 3
    duplicate["metricValue"] = 80.0
    package["categories"][0]["rows"].append(duplicate)
    package["categories"][0]["candidateCount"] = 3
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
    package["categories"][0]["candidateCount"] = 3
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
