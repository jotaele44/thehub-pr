"""Tests for the registry drift-detection tool.

Standalone (no `hub` import) so it also passes under the registry-only CI
workflow that installs just jsonschema/pyyaml/pytest.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "check_registry_drift.py"
REGISTRY = REPO_ROOT / "mcp" / "registry" / "capability_registry.yaml"
MANIFESTS = REPO_ROOT / "mcp" / "manifests"


def _run(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        capture_output=True, text=True,
    )


def test_committed_registry_has_no_drift():
    result = _run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "No registry drift" in result.stdout


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    reg = tmp_path / "capability_registry.yaml"
    mani = tmp_path / "manifests"
    shutil.copy(REGISTRY, reg)
    shutil.copytree(MANIFESTS, mani)
    return reg, mani


def test_missing_declaration_is_drift(tmp_path):
    reg, mani = _fixture(tmp_path)
    # Remove 'weather' from centinelas (registry still lists it required_by).
    path = mani / "centinelas.mcp.yaml"
    data = yaml.safe_load(path.read_text())
    data["capabilities"] = [c for c in data["capabilities"] if c != "weather"]
    path.write_text(yaml.safe_dump(data))

    result = _run("--registry", str(reg), "--manifests", str(mani))
    assert result.returncode == 1
    assert "centinelas" in result.stdout and "weather" in result.stdout


def test_extra_declaration_is_drift(tmp_path):
    reg, mani = _fixture(tmp_path)
    # spiderweb declares 'contracts' (a global cap it is not required_by).
    path = mani / "spiderweb.mcp.yaml"
    data = yaml.safe_load(path.read_text())
    data["capabilities"] = data["capabilities"] + ["contracts"]
    path.write_text(yaml.safe_dump(data))

    result = _run("--registry", str(reg), "--manifests", str(mani))
    assert result.returncode == 1
    assert "spiderweb" in result.stdout and "contracts" in result.stdout


def test_required_by_project_without_manifest_is_drift(tmp_path):
    reg, mani = _fixture(tmp_path)
    # Add a project to weather.required_by that has no manifest at all.
    data = yaml.safe_load(reg.read_text())
    data["capabilities"]["weather"]["required_by"].append("ghost-project")
    reg.write_text(yaml.safe_dump(data))

    result = _run("--registry", str(reg), "--manifests", str(mani))
    assert result.returncode == 1
    assert "ghost-project" in result.stdout
    assert "no manifest" in result.stdout


def test_project_local_capabilities_are_not_drift(tmp_path):
    # The committed manifests declare project-local caps (satellite, parcels,
    # etc.) that are absent from the registry; these must NOT be flagged.
    reg, mani = _fixture(tmp_path)
    result = _run("--registry", str(reg), "--manifests", str(mani))
    assert result.returncode == 0
