"""Tests for the registry sync report tool. Standalone (no `hub` import)."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "registry_sync_report.py"
REGISTRY = REPO_ROOT / "mcp" / "registry" / "capability_registry.yaml"
MANIFESTS = REPO_ROOT / "mcp" / "manifests"


def _run(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL), *args], capture_output=True, text=True
    )


def test_committed_registry_is_in_sync():
    result = _run()
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["in_sync"] is True
    assert report["drift"] == []
    assert report["project_count"] == 6
    # every project's declared global caps equal its expected set
    for project in report["projects"].values():
        assert project["missing"] == []
        assert project["extra"] == []


def test_report_flags_drift(tmp_path):
    reg = tmp_path / "capability_registry.yaml"
    mani = tmp_path / "manifests"
    shutil.copy(REGISTRY, reg)
    shutil.copytree(MANIFESTS, mani)
    # drop 'utilities' from aguayluz (registry still lists it required_by)
    path = mani / "aguayluz.mcp.yaml"
    data = yaml.safe_load(path.read_text())
    data["capabilities"] = [c for c in data["capabilities"] if c != "utilities"]
    path.write_text(yaml.safe_dump(data))

    result = _run("--registry", str(reg), "--manifests", str(mani))
    report = json.loads(result.stdout)
    assert report["in_sync"] is False
    assert any("utilities" in d for d in report["drift"])
    assert report["projects"]["aguayluz"]["missing"] == ["utilities"]


def test_report_writes_out_file(tmp_path):
    out = tmp_path / "report.json"
    result = _run("--out", str(out))
    assert result.returncode == 0
    report = json.loads(out.read_text())
    assert report["in_sync"] is True
