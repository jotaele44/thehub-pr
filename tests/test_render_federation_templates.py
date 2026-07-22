"""Tests for the federation boilerplate renderer (tools/render_federation_templates.py).

Runs in thehub CI where the producer sibling checkouts are absent, so these cover
the renderer logic + manifest integrity + thehub's own committed files (thehub is
checked out). The cross-repo byte-equality is enforced in each producer by its
template-drift.yml workflow.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

_HUB = Path(__file__).resolve().parents[1]
_TEMPLATES = _HUB / "federation-templates"
_RENDER = _HUB / "tools" / "render_federation_templates.py"


def _vars():
    return yaml.safe_load((_TEMPLATES / "producers.vars.yaml").read_text())["producers"]


def _targets():
    return yaml.safe_load((_TEMPLATES / "targets.yaml").read_text())["targets"]


def test_every_referenced_template_exists():
    for t in _targets():
        assert (_TEMPLATES / t["template"]).is_file(), t["template"]


def test_every_repo_in_targets_has_vars():
    known = set(_vars())
    for t in _targets():
        for repo in t["repos"]:
            assert repo in known, f"{repo} in targets.yaml but missing from vars"


def test_slug_substitution_renders_to_tmp(tmp_path):
    # Render ovnis into a temp root and confirm the .sh got the slug + the .command
    # is verbatim (slug only in the filename).
    r = subprocess.run(
        [sys.executable, str(_RENDER), "--repo", "ovnis-pr", "--repo-root", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    sh = (tmp_path / "PRII-OVNIS.sh").read_text()
    assert "PRII-OVNIS.sh" in sh and "{{APP_SLUG}}" not in sh
    assert (tmp_path / "PRII-OVNIS.command").is_file()
    assert (tmp_path / "schemas" / "federation_export_manifest.schema.json").is_file()


def test_check_detects_lost_executable_bit(tmp_path):
    # Render ovnis, then drop the exec bit on a launcher — --check must flag drift.
    subprocess.run(
        [sys.executable, str(_RENDER), "--repo", "ovnis-pr", "--repo-root", str(tmp_path)],
        check=True, capture_output=True,
    )
    launcher = tmp_path / "PRII-OVNIS.sh"
    launcher.chmod(0o644)  # content unchanged, exec bit removed
    r = subprocess.run(
        [sys.executable, str(_RENDER), "--repo", "ovnis-pr", "--check", "--repo-root", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert r.returncode == 1 and "PRII-OVNIS.sh" in r.stdout, r.stdout + r.stderr


def test_thehub_own_files_match_templates():
    # thehub is checked out here, so --repo-root . check its own launchers/schema.
    r = subprocess.run(
        [sys.executable, str(_RENDER), "--repo", "thehub-pr", "--check", "--repo-root", str(_HUB)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
