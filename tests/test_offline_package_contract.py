from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_offline_package_contract",
    ROOT / "scripts" / "validate_offline_package_contract.py",
)
VALIDATOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(VALIDATOR)


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _manifest() -> dict:
    return {
        "schema_version": "federation.offline_package.v1",
        "repo": "thehub-pr",
        "node_type": "hub",
        "data_mode": "live",
        "production_status": "production_candidate",
        "offline_ready": True,
        "localhost_required": False,
        "summary": {
            "records": 1,
            "sources": 1,
            "blockers_open": 0,
            "critical_blockers_open": 0,
            "evidence_items": 1,
        },
        "gates": {
            "tests": "not_applicable",
            "schema_validation": "unknown",
            "export_generated": "pass",
            "offline_dashboard_generated": "pass",
            "hub_ingest_compatible": "unknown",
        },
        "files": [{"path": "sources.json", "sha256": "a" * 64}],
    }


def test_manifest_gate_statuses_are_validated_per_field(tmp_path: Path) -> None:
    manifest = _manifest()
    _write_json(tmp_path / "manifest.json", manifest)
    errors: list[str] = []
    VALIDATOR.validate_manifest(tmp_path, errors)
    assert errors == []

    for key in ("schema_validation", "export_generated", "offline_dashboard_generated"):
        invalid = _manifest()
        invalid["gates"][key] = "not_applicable"
        _write_json(tmp_path / "manifest.json", invalid)
        errors = []
        VALIDATOR.validate_manifest(tmp_path, errors)
        assert f"manifest.gates.{key} invalid" in errors


def test_manifest_sha256_requires_lowercase_hex(tmp_path: Path) -> None:
    for malformed in ("G" * 64, "A" * 64, "a" * 63):
        manifest = _manifest()
        manifest["files"][0]["sha256"] = malformed
        _write_json(tmp_path / "manifest.json", manifest)
        errors: list[str] = []
        VALIDATOR.validate_manifest(tmp_path, errors)
        assert "manifest.files sha invalid for sources.json" in errors


def test_sources_accept_complete_schema_vocabulary(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "sources.json",
        {
            "schema_version": "federation.sources.v1",
            "repo": "thehub-pr",
            "sources": [
                {
                    "source_id": "source-1",
                    "name": "Example",
                    "category": "web",
                    "access_method": "scrape",
                    "scope": "puerto_rico",
                    "authority_level": "official",
                    "cadence": "event_driven",
                    "status": "blocked",
                    "notes": "Access is currently blocked.",
                }
            ],
        },
    )
    errors: list[str] = []
    VALIDATOR.validate_sources(tmp_path, "thehub-pr", errors)
    assert errors == []
