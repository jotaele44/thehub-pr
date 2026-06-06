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
