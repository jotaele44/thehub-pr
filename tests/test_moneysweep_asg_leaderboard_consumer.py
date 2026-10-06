from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi import HTTPException

from server.backend import moneysweep_asg_leaderboards as consumer


def _real_package() -> dict:
    return json.loads(consumer.DEFAULT_PACKAGE.read_text(encoding="utf-8"))


def test_exact_committed_asg_package_passes_contract():
    package = _real_package()
    assert consumer._validate_package(package) == []
    category = package["categories"][0]
    assert category["accounting"] == {
        "inputRecords": 1431,
        "outOfScopeRecords": 1410,
        "retainedRecords": 21,
        "excludedRecords": 0,
        "unresolvedRecords": 0,
        "inScopeRecords": 21,
        "arithmeticClosed": True,
    }
    assert category["candidateCount"] == 10
    assert round(sum(row["metricValue"] for row in category["rows"]), 2) == 4423664.82
    assert sum(row["recordCount"] for row in category["rows"]) == 21


def test_consumer_owned_trust_binds_exact_asg_package(monkeypatch):
    for name in consumer._TRUST_FIELDS:
        monkeypatch.delenv(name, raising=False)
    loaded = consumer._load_package()
    expected = hashlib.sha256(consumer.DEFAULT_PACKAGE.read_bytes()).hexdigest()
    assert loaded["consumerPackageSha256"] == expected
    assert expected == "6ecdad09a48cdbd4ae1076138a9b5017a5be82608b489871a50ce0d599680337"


def test_asg_accounting_scope_drift_is_rejected():
    package = _real_package()
    package["categories"][0]["accounting"]["outOfScopeRecords"] = 1409
    assert (
        "categories.asg_emergency_purchase_source_native.accounting.outOfScopeRecords"
        in consumer._validate_package(package)
    )


def test_name_only_or_canonical_identity_is_rejected():
    package = _real_package()
    row = package["categories"][0]["rows"][0]
    row["entityResolutionState"] = "UNRESOLVED_NAME_ONLY"
    row["canonicalEntityId"] = "entity_unsafe"
    errors = consumer._validate_package(package)
    assert "categories.asg_emergency_purchase_source_native.identityState" in errors
    assert "categories.asg_emergency_purchase_source_native.canonicalEntityId" in errors


def test_source_ordering_and_universe_drift_are_rejected():
    package = _real_package()
    source = package["categories"][0]["sourceVersion"]
    source["ordering"] = "-creado"
    source["authoritativeUniverseTotal"] = 1319
    errors = consumer._validate_package(package)
    assert "categories.asg_emergency_purchase_source_native.ordering" in errors
    assert "categories.asg_emergency_purchase_source_native.authoritativeUniverseTotal" in errors


def test_control_and_record_arithmetic_is_rejected_on_tamper():
    package = _real_package()
    row = package["categories"][0]["rows"][0]
    row["recordCount"] += 1
    errors = consumer._validate_package(package)
    assert "categories.asg_emergency_purchase_source_native.recordCount" in errors
    assert "categories.asg_emergency_purchase_source_native.retainedControlArithmetic" in errors


def test_metric_total_tamper_is_rejected():
    package = _real_package()
    package["categories"][0]["rows"][0]["metricValue"] += 1
    assert (
        "categories.asg_emergency_purchase_source_native.metricTotal"
        in consumer._validate_package(package)
    )


def test_untrusted_package_hash_fails_closed(tmp_path: Path, monkeypatch):
    path = tmp_path / "package.json"
    package = _real_package()
    package["categories"][0]["rows"][0]["metricValue"] += 1
    path.write_text(json.dumps(package), encoding="utf-8")
    for name in consumer._TRUST_FIELDS:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(HTTPException) as exc:
        consumer._load_package(path)
    assert exc.value.status_code == 409


def test_top_preserves_producer_rows_and_scope_boundary():
    package = _real_package()
    response = consumer.top(limit=25)
    assert response["rows"] == package["categories"][0]["rows"]
    assert response["consumerState"] == "PASS"
    assert "does not represent all ASG emergency purchases" in response["scopeBoundary"]


def test_main_mounts_asg_route_before_spa_alias():
    main_path = Path(__file__).resolve().parents[1] / "server" / "backend" / "main.py"
    source = main_path.read_text(encoding="utf-8")
    mount = 'raise RuntimeError("MoneySweep ASG leaderboard consumer route failed to mount on canonical FastAPI app")'
    reorder = "Leaderboard routes are mounted after the core SPA catch-all"
    alias = "sys.modules[__name__] = _core"
    assert mount in source
    assert source.index(mount) < source.index(reorder) < source.index(alias)
