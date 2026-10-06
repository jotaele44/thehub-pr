from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from server.backend import moneysweep_asg_leaderboards as consumer


def _package() -> dict:
    cert_runtime = {
        "schemaVersion": "moneysweep.leaderboard-certification-runtime/v1",
        "state": "FROZEN",
        "files": [
            {
                "path": "scripts/export_leaderboard_package.py",
                "bytes": 10,
                "sha256": "1" * 64,
            }
        ],
    }
    rows = [
        {
            "entityId": "asg_licitador_id:23388",
            "canonicalEntityId": None,
            "entityDisplayName": "Sonnell Truck Center LLC",
            "entityResolutionState": "SOURCE_NATIVE_ASG_LICITADOR_ID",
            "metricType": "ASG_EMERGENCY_PURCHASE_COST",
            "metricValue": 1744085.0,
            "currency": "USD",
            "rank": 1,
            "recordCount": 1,
        },
        {
            "entityId": "asg_licitador_id:56227",
            "canonicalEntityId": None,
            "entityDisplayName": "Duenas Leasing LLC",
            "entityResolutionState": "SOURCE_NATIVE_ASG_LICITADOR_ID",
            "metricType": "ASG_EMERGENCY_PURCHASE_COST",
            "metricValue": 1474425.0,
            "currency": "USD",
            "rank": 2,
            "recordCount": 2,
        },
    ]
    # Fill the remaining eight entities while conserving 21 source rows.
    totals = [
        ("10329", "La Casa del Camionero", 297908.8, 4),
        ("28546", "A1 Generator Services Incorporated", 293629.35, 7),
        ("1174", "Autos Vega Inc.", 278050.0, 1),
        ("303", "Teselta LLC", 187180.0, 2),
        ("437", "Mendez & Co.", 71003.52, 1),
        ("4381", "Caribbean Composting Inc.", 47200.0, 1),
        ("13947", "ALL GREEN CLEANING & MAINTENANCE, LLC", 20624.4, 1),
        ("25833", "Almacen El Ahorro LLC", 9558.75, 1),
    ]
    for position, (rid, name, value, count) in enumerate(totals, start=3):
        rows.append(
            {
                "entityId": f"asg_licitador_id:{rid}",
                "canonicalEntityId": None,
                "entityDisplayName": name,
                "entityResolutionState": "SOURCE_NATIVE_ASG_LICITADOR_ID",
                "metricType": "ASG_EMERGENCY_PURCHASE_COST",
                "metricValue": value,
                "currency": "USD",
                "rank": position,
                "recordCount": count,
            }
        )

    return {
        "schemaVersion": "moneysweep.leaderboard-export-package/v1",
        "producer": "moneysweep-pr",
        "producerCommit": "a" * 40,
        "rankingContractVersion": "moneysweep.leaderboard/v1.1",
        "ontologyContractVersion": "moneysweep.financial-category-ontology/v1.2",
        "scopeId": "moneysweep.leaderboard.asg-source-native-v1",
        "generatedAt": "2026-10-06T05:00:00+00:00",
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
                "categoryId": "asg_emergency_purchase_source_native",
                "metricType": "ASG_EMERGENCY_PURCHASE_COST",
                "snapshotId": "asg-snapshot-1",
                "snapshotSha256": "e" * 64,
                "capturedAt": "2026-10-06T04:43:07+00:00",
                "candidateCount": 10,
                "accounting": {
                    "inputRecords": 1431,
                    "outOfScopeRecords": 1410,
                    "retainedRecords": 21,
                    "excludedRecords": 0,
                    "unresolvedRecords": 0,
                    "inScopeRecords": 21,
                    "arithmeticClosed": True,
                },
                "sourceVersion": {
                    "type": "LIVE_PORTAL_MATERIALIZATION",
                    "sourceId": "asg_emergency_purchases",
                    "capturedAt": "2026-10-06T04:43:07+00:00",
                    "ordering": "numerocontrol",
                    "authoritativeUniverseTotal": 1431,
                    "sourceSha256": "2" * 64,
                    "rawBundleSha256": "2" * 64,
                    "economicActivityInference": False,
                },
                "sourceManifestations": [
                    {"path": "source_native_rows_v1.csv", "bytes": 10, "sha256": "3" * 64},
                    {"path": "materialization_receipt.json", "bytes": 10, "sha256": "4" * 64},
                    {
                        "path": "public/static/asg.jsonl",
                        "bytes": 100,
                        "sha256": "5" * 64,
                        "manifestationType": "FLOOT_OBJECT_STORAGE_AUTHORITATIVE_CORPUS",
                    },
                    {
                        "path": "public/static/asg_pages.json",
                        "bytes": 100,
                        "sha256": "6" * 64,
                        "manifestationType": "FLOOT_OBJECT_STORAGE_PAGE_MANIFEST",
                    },
                    {
                        "path": "public/static/asg_suppliers.json",
                        "bytes": 100,
                        "sha256": "7" * 64,
                        "manifestationType": "FLOOT_OBJECT_STORAGE_SUPPLIER_ID_VERIFICATION",
                    },
                ],
                "runtimeManifest": {
                    "state": "FROZEN",
                    "producerCommit": "a" * 40,
                    "files": [
                        {
                            "path": "server/backend/leaderboard_adapters.py",
                            "bytes": 30,
                            "sha256": "8" * 64,
                        }
                    ],
                },
                "snapshotCertification": {
                    "state": "PASS",
                    "scopeId": "moneysweep.leaderboard.asg-source-native-v1",
                    "sourceSnapshotSha256": "9" * 64,
                    "zeroMaterialUnresolvedResidue": True,
                },
                "rows": rows,
            }
        ],
    }


def _write(path: Path, package: dict | None = None) -> dict:
    value = package or _package()
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return value


def _trust(monkeypatch, path: Path) -> None:
    monkeypatch.setenv("PRII_MONEYSWEEP_ASG_LEADERBOARD_RECEIPT_SHA256", "b" * 64)
    monkeypatch.setenv("PRII_MONEYSWEEP_ASG_LEADERBOARD_RELEASE_SHA256", "c" * 64)
    monkeypatch.setenv("PRII_MONEYSWEEP_ASG_LEADERBOARD_SCOPE_SHA256", "d" * 64)
    monkeypatch.setenv(
        "PRII_MONEYSWEEP_ASG_LEADERBOARD_PACKAGE_SHA256",
        hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def test_missing_package_fails_closed(tmp_path: Path):
    with pytest.raises(HTTPException) as exc:
        consumer._load_package(tmp_path / "missing.json")
    assert exc.value.status_code == 409
    assert exc.value.detail["state"] == "BLOCKED"


def test_exact_asg_package_contract_passes():
    assert consumer._validate_package(_package()) == []


def test_bounded_accounting_drift_is_rejected():
    package = _package()
    package["categories"][0]["accounting"]["outOfScopeRecords"] = 1409
    assert (
        "categories.asg_emergency_purchase_source_native.accounting.outOfScopeRecords"
        in consumer._validate_package(package)
    )


def test_name_or_canonical_identity_promotion_is_rejected():
    package = _package()
    row = package["categories"][0]["rows"][0]
    row["entityResolutionState"] = "NAME_ONLY"
    row["canonicalEntityId"] = "entity-promoted"
    errors = consumer._validate_package(package)
    assert "categories.asg_emergency_purchase_source_native.identityState" in errors
    assert "categories.asg_emergency_purchase_source_native.canonicalEntityPromotion" in errors


def test_live_source_contract_drift_is_rejected():
    package = _package()
    source = package["categories"][0]["sourceVersion"]
    source["ordering"] = "-creado"
    source["authoritativeUniverseTotal"] = 1319
    errors = consumer._validate_package(package)
    assert "categories.asg_emergency_purchase_source_native.sourceVersionOrdering" in errors
    assert "categories.asg_emergency_purchase_source_native.sourceVersionUniverse" in errors


def test_required_source_manifestations_are_enforced():
    package = _package()
    package["categories"][0]["sourceManifestations"] = package["categories"][0]["sourceManifestations"][:2]
    assert (
        "categories.asg_emergency_purchase_source_native.sourceManifestationTypes"
        in consumer._validate_package(package)
    )


def test_record_count_conservation_and_competition_rank_are_enforced():
    package = _package()
    package["categories"][0]["rows"][0]["recordCount"] = 2
    package["categories"][0]["rows"][1]["rank"] = 1
    errors = consumer._validate_package(package)
    assert "categories.asg_emergency_purchase_source_native.recordCountConservation" in errors
    assert "categories.asg_emergency_purchase_source_native.competitionRank" in errors


def test_trusted_package_preserves_producer_rows(tmp_path: Path, monkeypatch):
    path = tmp_path / "asg.json"
    package = _write(path)
    _trust(monkeypatch, path)
    loaded = consumer._load_package(path)
    assert loaded["categories"][0]["rows"] == package["categories"][0]["rows"]
    assert loaded["scopeId"] == consumer.EXPECTED_SCOPE


def test_debt_trust_environment_does_not_authorize_asg(tmp_path: Path, monkeypatch):
    path = tmp_path / "asg.json"
    _write(path)
    monkeypatch.setattr(consumer, "DEFAULT_TRUST", tmp_path / "missing-trust.json")
    monkeypatch.setenv("PRII_MONEYSWEEP_LEADERBOARD_RECEIPT_SHA256", "b" * 64)
    monkeypatch.setenv("PRII_MONEYSWEEP_LEADERBOARD_RELEASE_SHA256", "c" * 64)
    monkeypatch.setenv("PRII_MONEYSWEEP_LEADERBOARD_SCOPE_SHA256", "d" * 64)
    monkeypatch.setenv(
        "PRII_MONEYSWEEP_LEADERBOARD_PACKAGE_SHA256",
        hashlib.sha256(path.read_bytes()).hexdigest(),
    )
    with pytest.raises(HTTPException) as exc:
        consumer._load_package(path)
    assert exc.value.detail["state"] == "BLOCKED"
    assert exc.value.detail["receiptTrusted"] is False
    assert exc.value.detail["packageTrusted"] is False


def test_asg_route_is_mounted_before_spa_fallback():
    main_path = Path(__file__).resolve().parents[1] / "server" / "backend" / "main.py"
    source = main_path.read_text(encoding="utf-8")
    import_marker = "from server.backend.moneysweep_asg_leaderboards import router as _moneysweep_asg_leaderboards_router"
    mount_marker = 'raise RuntimeError("MoneySweep ASG leaderboard consumer route failed to mount on canonical FastAPI app")'
    ordering_marker = "both debt and ASG consumer routes"
    alias_marker = "sys.modules[__name__] = _core"
    assert import_marker in source
    assert mount_marker in source
    assert ordering_marker in source
    assert source.index(mount_marker) < source.index(ordering_marker) < source.index(alias_marker)
