"""Tests for the cross-repo sync artifact generator. Standalone (no hub)."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "generate_sync_artifacts.py"
REGISTRY = REPO_ROOT / "mcp" / "registry" / "capability_registry.yaml"

_spec = importlib.util.spec_from_file_location("gen_sync", TOOL)
gen_sync = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen_sync)


def test_artifacts_cover_all_six_producers():
    artifacts = gen_sync.build_artifacts(REGISTRY)
    assert set(artifacts) == {
        "skywatcher", "ovnis", "spiderweb", "centinelas", "moneysweep", "aguayluz",
    }
    for project, artifact in artifacts.items():
        assert artifact["project"] == project
        assert artifact["hub"] == "thehub-pr"
        assert isinstance(artifact["expected_capabilities"], list)


def test_expected_matches_required_by():
    registry = yaml.safe_load(REGISTRY.read_text())
    artifacts = gen_sync.build_artifacts(REGISTRY)
    # moneysweep should expect exactly the caps whose required_by includes it.
    expected = sorted(
        name for name, spec in registry["capabilities"].items()
        if "moneysweep" in (spec.get("required_by") or [])
    )
    assert artifacts["moneysweep"]["expected_capabilities"] == expected
    assert "contracts" in expected  # sanity


def test_out_dir_writes_one_file_per_producer(tmp_path):
    result = subprocess.run(
        [sys.executable, str(TOOL), "--out-dir", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    files = sorted(p.name for p in tmp_path.glob("*.capabilities.json"))
    assert len(files) == 6
    sample = json.loads((tmp_path / "aguayluz.capabilities.json").read_text())
    assert sample["project"] == "aguayluz"
    assert "utilities" in sample["expected_capabilities"]


def test_stdout_is_valid_json():
    result = subprocess.run(
        [sys.executable, str(TOOL)], capture_output=True, text=True
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert len(data) == 6
