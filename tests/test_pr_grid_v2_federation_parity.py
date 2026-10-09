"""Tests for strict six-consumer PR grid V2 parity validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validate_pr_grid_v2_federation_pins import PinParityError, validate

ROOT = Path(__file__).resolve().parents[1]
DENOM = json.loads((ROOT / "registry/pr_grid_v2_consumers.json").read_text())


def _pin_for(consumer: dict) -> dict:
    return {
        "schema_version": "pr_grid_geographic_v2_consumer_pin/1.0",
        "consumer": consumer["repo"],
        "geometry_authority": "spiderweb-pr",
        "authority_repository": DENOM["authority_repository"],
        "authority_commit": DENOM["authority_commit"],
        "authority_manifest_path": "registry/spatial/v2/pr_grid_geographic_v2.manifest.json",
        "grid_id": DENOM["grid_id"],
        "grid_version": DENOM["grid_version"],
        "crs": "EPSG:6566",
        "grid_manifest_sha256": DENOM["grid_manifest_sha256"],
        "cell_schema_sha256": DENOM["cell_schema_sha256"],
        "binding_schema_sha256": DENOM["binding_schema_sha256"],
        "binding_schema_version": "pr-grid-v2-binding/1.0",
        "mask_schema_sha256": DENOM["mask_schema_sha256"],
        "mask_schema_version": "pr-grid-v2-mask/1.0",
        "default_level": consumer["default_level"],
        "allowed_levels": ["L0", "L1", "L2", "L3"],
        "geometry_mode": "REFERENCE_ONLY",
        "local_geometry_copy": False,
        "v1_coexistence": "PRESERVE_UNCHANGED",
        "compatibility_policy": "FAIL_CLOSED",
        "external_provider_blockers": [
            {"id": "QA-D24-001", "affects_grid_identity": False},
            {"id": "QA-D24-003", "affects_grid_identity": False},
        ],
    }


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    federation_root = tmp_path / "_federation"
    self_root = tmp_path / "thehub-pr"
    denominator = tmp_path / "denominator.json"
    denominator.write_text(json.dumps(DENOM), encoding="utf-8")

    for consumer in DENOM["consumers"]:
        root = self_root if consumer["repo"] == "thehub-pr" else federation_root / consumer["repo"]
        target = root / "federation/spatial"
        target.mkdir(parents=True)
        (target / "pr_grid_geographic_v2.pin.json").write_text(
            json.dumps(_pin_for(consumer)),
            encoding="utf-8",
        )
    return federation_root, self_root, denominator


def test_six_consumer_denominator_closes_exactly(tmp_path):
    federation_root, self_root, denominator = _fixture(tmp_path)
    result = validate(
        denominator_path=denominator,
        federation_root=federation_root,
        self_root=self_root,
        require_all=True,
    )
    assert result["state"] == "PASS"
    assert result["denominator"] == 6
    assert result["pass_count"] == 6
    assert result["missing_count"] == 0
    assert result["divergent_count"] == 0


def test_divergent_hash_fails_closed(tmp_path):
    federation_root, self_root, denominator = _fixture(tmp_path)
    path = federation_root / "moneysweep-pr/federation/spatial/pr_grid_geographic_v2.pin.json"
    payload = json.loads(path.read_text())
    payload["grid_manifest_sha256"] = "0" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PinParityError):
        validate(
            denominator_path=denominator,
            federation_root=federation_root,
            self_root=self_root,
            require_all=True,
        )


def test_missing_consumer_fails_when_require_all(tmp_path):
    federation_root, self_root, denominator = _fixture(tmp_path)
    path = federation_root / "ovnis-pr/federation/spatial/pr_grid_geographic_v2.pin.json"
    path.unlink()

    with pytest.raises(PinParityError):
        validate(
            denominator_path=denominator,
            federation_root=federation_root,
            self_root=self_root,
            require_all=True,
        )
