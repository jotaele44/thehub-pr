from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hub.federation_runtime import (
    AGUAYLUZ_REPOSITORY,
    REQUIRED_CONTROL_PATHS,
    REQUIRED_RUNTIME_PATHS,
    FederationRuntimeError,
    load_federation_runtime_manifest,
    validate_federation_runtime_manifest,
)
from hub.spatial import REQUIRED_CERTIFICATION_GATES


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _spatial_manifest(state="PASS"):
    return {
        "contract_version": "federation-spatial-manifest/1.0",
        "producer_repo": "aguayluz-pr",
        "frozen_base_sha": "c" * 40,
        "authority": "water power environmental infrastructure",
        "contracts": {"feature": "schemas/federation_spatial_feature_v1.schema.json"},
        "storage": {"ownership": "REPO_LOCAL"},
        "cross_repo": {
            "identity_default": "CANDIDATE_NOT_IDENTITY",
            "hub_correlation_authority": "thehub-pr",
        },
        "gates": {gate: state for gate in REQUIRED_CERTIFICATION_GATES},
    }


def _control_documents(spatial_state="PASS"):
    return {
        "federation.spatial.json": _spatial_manifest(spatial_state),
        ".federation/haf_contract.json": {
            "repository_full_name": AGUAYLUZ_REPOSITORY,
            "certification_required": True,
            "identity_policy": "EVIDENCE_PRIORITY_FAIL_CLOSED",
            "unresolved_policy": "FAIL_CLOSED",
            "adapter_release_version": "0.5.0",
            "haf_contract_version": "2.0.0",
        },
        "governance/federation_compatibility.json": {
            "repo": "aguayluz-pr",
            "disposition": "COMPATIBLE",
        },
        "governance/federation_gis_retention_v1.json": {
            "repository": AGUAYLUZ_REPOSITORY,
            "source_pr": 209,
            "expected_path_count": 20,
        },
    }


def _write_package(tmp_path: Path, *, spatial_state="PASS") -> tuple[dict, Path]:
    root = tmp_path / "package"
    runtime_receipts = []
    for index, rel in enumerate(sorted(REQUIRED_RUNTIME_PATHS)):
        data = json.dumps({"fixture": index}, sort_keys=True).encode()
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        runtime_receipts.append(
            {"path": rel, "bytes": len(data), "sha256": _sha256(data)}
        )

    control_receipts = []
    for rel, doc in _control_documents(spatial_state).items():
        data = (json.dumps(doc, sort_keys=True) + "\n").encode()
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        control_receipts.append(
            {
                "path": rel,
                "bytes": len(data),
                "sha256": _sha256(data),
                "git_blob_sha": "d" * 40,
            }
        )

    manifest = {
        "schema_version": "aguayluz_federation_runtime_freeze_v1",
        "repository": AGUAYLUZ_REPOSITORY,
        "producer_commit": "a" * 40,
        "producer_tree": "b" * 40,
        "generated_utc": "2026-09-05T00:00:00Z",
        "mode": "CERTIFICATION",
        "test_receipt": {
            "gate_id": "G08_EXECUTED_TEST_RECEIPT",
            "status": "PASS",
            "details": "FULL pytest receipt bound to producer commit/tree",
        },
        "spatial_certification": {
            "ok": spatial_state == "PASS",
            "certification_ready": spatial_state == "PASS",
            "certification_state": "PASS" if spatial_state == "PASS" else "BLOCKED",
        },
        "counts": {
            "utility_assets": 3,
            "service_events": 2,
            "records_total": 5,
            "source_manifest_entries": 2,
            "review_queue_items": 0,
            "canonical_streams": {
                "sources": 2,
                "entities": 5,
                "relationships": 4,
                "alerts": 1,
            },
        },
        "files": runtime_receipts,
        "file_count": len(runtime_receipts),
        "control_plane_files": control_receipts,
        "control_plane_file_count": len(control_receipts),
        "certification_eligible": spatial_state == "PASS",
        "problems": [],
        "state": "PASS" if spatial_state == "PASS" else "AUDIT_ONLY",
    }
    manifest_path = root / "artifacts/federation_certification/runtime_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest, root


def test_exact_byte_certification_accepts_complete_pass_package(tmp_path):
    manifest, root = _write_package(tmp_path, spatial_state="PASS")
    errors = validate_federation_runtime_manifest(
        manifest, package_root=root, certification=True
    )
    assert errors == []

    package = load_federation_runtime_manifest(
        root / "artifacts/federation_certification/runtime_manifest.json",
        package_root=root,
        certification=True,
    )
    assert package.promotable is True
    assert package.ingestion_mode == "CERTIFIED"


def test_audit_accepts_coherent_open_spatial_state_but_never_promotes(tmp_path):
    manifest, root = _write_package(tmp_path, spatial_state="OPEN")
    manifest["mode"] = "EVIDENCE_ONLY"
    manifest["certification_eligible"] = False
    manifest["state"] = "AUDIT_ONLY"
    path = root / "artifacts/federation_certification/runtime_manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    package = load_federation_runtime_manifest(path, package_root=root)
    assert package.promotable is False
    assert package.ingestion_mode == "AUDIT_ONLY"

    with pytest.raises(FederationRuntimeError):
        load_federation_runtime_manifest(path, package_root=root, certification=True)


def test_exact_byte_validation_rejects_mutated_payload(tmp_path):
    manifest, root = _write_package(tmp_path, spatial_state="PASS")
    target = root / "outputs/hub_export.json"
    target.write_bytes(target.read_bytes() + b"mutated")
    errors = validate_federation_runtime_manifest(
        manifest, package_root=root, certification=True
    )
    assert any("hub_export.json" in error and "mismatch" in error for error in errors)


def test_runtime_manifest_rejects_unsafe_duplicate_and_missing_paths(tmp_path):
    manifest, _ = _write_package(tmp_path, spatial_state="PASS")
    manifest["files"][0]["path"] = "../escape.json"
    manifest["files"].append(dict(manifest["files"][1]))
    manifest["file_count"] = len(manifest["files"])
    errors = validate_federation_runtime_manifest(manifest, certification=False)
    assert any("unsafe" in error for error in errors)
    assert any("duplicate runtime files path" in error for error in errors)
    assert any("missing required paths" in error for error in errors)


def test_certification_rejects_blocked_compatibility_even_if_summary_claims_pass(tmp_path):
    manifest, root = _write_package(tmp_path, spatial_state="PASS")
    compatibility_path = root / "governance/federation_compatibility.json"
    compatibility = json.loads(compatibility_path.read_text())
    compatibility["disposition"] = "BLOCKED"
    data = (json.dumps(compatibility, sort_keys=True) + "\n").encode()
    compatibility_path.write_bytes(data)
    for receipt in manifest["control_plane_files"]:
        if receipt["path"] == "governance/federation_compatibility.json":
            receipt["bytes"] = len(data)
            receipt["sha256"] = _sha256(data)
    errors = validate_federation_runtime_manifest(
        manifest, package_root=root, certification=True
    )
    assert "federation compatibility is BLOCKED" in errors


def test_control_plane_path_set_is_exact():
    assert REQUIRED_CONTROL_PATHS == {
        "federation.spatial.json",
        ".federation/haf_contract.json",
        "governance/federation_compatibility.json",
        "governance/federation_gis_retention_v1.json",
    }
