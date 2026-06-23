"""Tests for federation_status: validate_federation() and ProducerReadiness."""
from __future__ import annotations

import json
from pathlib import Path


from hub.federation_status import _blocker_class, validate_federation
from hub.registry import Producer, Registry

_VALID_FEDERATION_JSON = {
    "schema_version": "repo_federation_manifest_v1",
    "program_id": "test-producer",
    "repository_full_name": "jotaele44/test-producer",
    "federation_role": "test_node",
    "hub_parent": "thehub-pr",
    "federation_readiness_gate": {
        "ready_for_hub_discovery": True,
        "ready_for_hub_live_execution": False,
        "blocking_conditions": ["synthetic data only"],
    },
    "hub_callable_commands": {
        "setup": "echo setup",
        "test_suite": "pytest",
        "export_canonical": "python scripts/export.py",
    },
    "canonical_outputs": {
        "federation": "exports/federation",
    },
}

_VALID_FEDERATION_JSON_LIVE = {
    **_VALID_FEDERATION_JSON,
    "federation_readiness_gate": {
        "ready_for_hub_discovery": True,
        "ready_for_hub_live_execution": True,
        "blocking_conditions": [],
    },
}


def _make_registry(producer_dir: Path) -> Registry:
    return Registry(
        hub="thehub-pr",
        schema_version="hub_registry_v1",
        producers=[
            Producer(
                program_id="test-producer",
                repo="jotaele44/test-producer",
                role="test_node",
                status="ready_for_discovery",
                local_path=str(producer_dir),
            )
        ],
    )


# ── _blocker_class unit tests ─────────────────────────────────────────────────

def test_blocker_class_missing_checkout():
    assert _blocker_class(
        checkout_present=False, manifest_present=False, manifest_valid=False,
        package_present=False, package_valid=False,
        live_execution_ready=False, declared_status="ready_for_discovery",
    ) == "missing_checkout"


def test_blocker_class_missing_manifest():
    assert _blocker_class(
        checkout_present=True, manifest_present=False, manifest_valid=False,
        package_present=False, package_valid=False,
        live_execution_ready=False, declared_status="ready_for_discovery",
    ) == "missing_manifest"


def test_blocker_class_invalid_manifest():
    assert _blocker_class(
        checkout_present=True, manifest_present=True, manifest_valid=False,
        package_present=False, package_valid=False,
        live_execution_ready=False, declared_status="ready_for_discovery",
    ) == "invalid_manifest"


def test_blocker_class_missing_export_package():
    assert _blocker_class(
        checkout_present=True, manifest_present=True, manifest_valid=True,
        package_present=False, package_valid=False,
        live_execution_ready=False, declared_status="ready_for_discovery",
    ) == "missing_export_package"


def test_blocker_class_invalid_export_package():
    assert _blocker_class(
        checkout_present=True, manifest_present=True, manifest_valid=True,
        package_present=True, package_valid=False,
        live_execution_ready=False, declared_status="ready_for_discovery",
    ) == "invalid_export_package"


def test_blocker_class_declared_not_live_when_live_execution_false():
    # valid package + valid manifest, but producer says live_execution_ready=False
    assert _blocker_class(
        checkout_present=True, manifest_present=True, manifest_valid=True,
        package_present=True, package_valid=True,
        live_execution_ready=False, declared_status="ready_for_discovery",
    ) == "declared_not_live"


def test_blocker_class_declared_not_live_via_declared_status():
    # live_execution_ready=True but declared_status is a block keyword
    assert _blocker_class(
        checkout_present=True, manifest_present=True, manifest_valid=True,
        package_present=True, package_valid=True,
        live_execution_ready=True, declared_status="blocked",
    ) == "declared_not_live"


def test_blocker_class_ready():
    assert _blocker_class(
        checkout_present=True, manifest_present=True, manifest_valid=True,
        package_present=True, package_valid=True,
        live_execution_ready=True, declared_status="ready_for_live",
    ) == "ready"


# ── validate_federation() integration tests ───────────────────────────────────

def test_validate_federation_missing_checkout(tmp_path):
    reg = _make_registry(tmp_path / "nonexistent")
    summary = validate_federation(reg, tmp_path)
    assert summary["producer_count"] == 1
    assert summary["ready_count"] == 0
    p = summary["producers"][0]
    assert p["blocker_class"] == "missing_checkout"
    assert p["live_execution_ready"] is False
    assert p["callable_commands"] == []
    assert p["last_package_timestamp"] is None


def test_validate_federation_extracts_live_execution_flag(tmp_path, valid_package):
    producer_dir = tmp_path / "prod"
    producer_dir.mkdir()
    (producer_dir / "federation.json").write_text(json.dumps(_VALID_FEDERATION_JSON))
    # place the valid package at the default export_path
    pkg_dst = producer_dir / "exports" / "federation"
    pkg_dst.mkdir(parents=True)
    for f in valid_package.iterdir():
        (pkg_dst / f.name).write_bytes(f.read_bytes())

    reg = _make_registry(producer_dir)
    summary = validate_federation(reg, tmp_path)
    p = summary["producers"][0]
    assert p["live_execution_ready"] is False
    assert p["blocker_class"] == "declared_not_live"


def test_validate_federation_extracts_callable_commands(tmp_path):
    producer_dir = tmp_path / "prod"
    producer_dir.mkdir()
    (producer_dir / "federation.json").write_text(json.dumps(_VALID_FEDERATION_JSON))

    reg = _make_registry(producer_dir)
    summary = validate_federation(reg, tmp_path)
    p = summary["producers"][0]
    assert sorted(p["callable_commands"]) == ["export_canonical", "setup", "test_suite"]


def test_validate_federation_extracts_package_timestamp(tmp_path, valid_package):
    producer_dir = tmp_path / "prod"
    producer_dir.mkdir()
    (producer_dir / "federation.json").write_text(json.dumps(_VALID_FEDERATION_JSON_LIVE))
    pkg_dst = producer_dir / "exports" / "federation"
    pkg_dst.mkdir(parents=True)
    for f in valid_package.iterdir():
        (pkg_dst / f.name).write_bytes(f.read_bytes())

    reg = _make_registry(producer_dir)
    summary = validate_federation(reg, tmp_path)
    p = summary["producers"][0]
    assert p["last_package_timestamp"] == "2026-01-01T00:00:00Z"


def test_validate_federation_ready_when_live_execution_true(tmp_path, valid_package):
    producer_dir = tmp_path / "prod"
    producer_dir.mkdir()
    (producer_dir / "federation.json").write_text(json.dumps(_VALID_FEDERATION_JSON_LIVE))
    pkg_dst = producer_dir / "exports" / "federation"
    pkg_dst.mkdir(parents=True)
    for f in valid_package.iterdir():
        (pkg_dst / f.name).write_bytes(f.read_bytes())

    reg = _make_registry(producer_dir)
    summary = validate_federation(reg, tmp_path)
    p = summary["producers"][0]
    assert p["live_execution_ready"] is True
    assert p["blocker_class"] == "ready"
    assert summary["ready_count"] == 1


def test_validate_federation_no_federation_json_defaults_to_not_live(tmp_path):
    producer_dir = tmp_path / "prod"
    producer_dir.mkdir()
    # no federation.json at all

    reg = _make_registry(producer_dir)
    summary = validate_federation(reg, tmp_path)
    p = summary["producers"][0]
    assert p["live_execution_ready"] is False
    assert p["callable_commands"] == []
