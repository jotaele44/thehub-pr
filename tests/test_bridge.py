import json

import pytest

from hub.bridge import write_manifest
from hub.validate import validate_package


def test_wrap_bridge_roundtrip(valid_package):
    """A directory of canonical JSONL streams + a generated manifest validates."""
    (valid_package / "manifest.json").unlink()
    manifest = write_manifest(valid_package, "moneysweep-pr", mode="test")
    assert manifest["package_id"].startswith("pkg_")
    assert manifest["federation"]["hub_parent"] == "thehub-pr"
    assert {f["stream"] for f in manifest["files"]} == {"sources", "entities", "relationships"}
    assert validate_package(valid_package) == []


def test_wrap_bridge_is_deterministic(valid_package):
    (valid_package / "manifest.json").unlink()
    a = write_manifest(valid_package, "moneysweep-pr", mode="test")
    b = write_manifest(valid_package, "moneysweep-pr", mode="test")
    assert a["package_id"] == b["package_id"]


def test_wrap_bridge_mode_changes_package_id(valid_package):
    (valid_package / "manifest.json").unlink()
    test_id = write_manifest(valid_package, "moneysweep-pr", mode="test")["package_id"]
    prod_id = write_manifest(valid_package, "moneysweep-pr", mode="production")["package_id"]
    assert test_id != prod_id


def test_wrap_bridge_empty_dir_raises(tmp_path):
    with pytest.raises(ValueError):
        write_manifest(tmp_path, "moneysweep-pr")


def test_wrap_bridge_includes_observations(tmp_path):
    """An observations-only stream dir is wrapped into a valid package."""
    _TS = "2026-01-01T00:00:00Z"
    lineage = {"producer_script": "x.py", "producer_phase": "TEST", "source_inputs": []}
    obs = {
        "observation_id": "obs_" + "0" * 32, "source_id": "src_" + "0" * 32,
        "observation_type": "aircraft_transit", "observed_at": _TS,
        "confidence": 0.9, "lineage": lineage, "synthetic": True,
        "created_at": _TS, "extracted_at": _TS,
    }
    (tmp_path / "observations.jsonl").write_text(json.dumps(obs, sort_keys=True) + "\n")
    manifest = write_manifest(tmp_path, "skywatcher-pr", mode="test")
    assert {f["stream"] for f in manifest["files"]} == {"observations"}
    assert validate_package(tmp_path) == []
