"""Tests for the federation boilerplate renderer (tools/render_federation_templates.py).

Runs in thehub CI where the producer sibling checkouts are absent, so these cover
the renderer logic + manifest integrity + thehub's own committed files (thehub is
checked out). The cross-repo byte-equality is enforced in each producer by its
template-drift.yml workflow.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import yaml

_HUB = Path(__file__).resolve().parents[1]
_TEMPLATES = _HUB / "federation-templates"
_RENDER = _HUB / "tools" / "render_federation_templates.py"


def _renderer():
    """Import the renderer as a module so the pure helpers can be unit-tested."""
    spec = importlib.util.spec_from_file_location("_render_fed", _RENDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


# ── Engineering baseline (Dependabot / CodeQL / secret-scan / pip-audit) ───────


def test_per_repo_vars_substitute_beyond_the_slug(tmp_path):
    # npm_dir differs per repo (dashboard/ vs frontend/ vs server/frontend/), so a
    # renderer that only knew about app_slug would point Dependabot at the wrong
    # tree in five of seven repos and silently watch nothing.
    subprocess.run(
        [sys.executable, str(_RENDER), "--repo", "spiderweb-pr", "--repo-root", str(tmp_path)],
        check=True, capture_output=True,
    )
    dependabot = yaml.safe_load((tmp_path / ".github" / "dependabot.yml").read_text())
    npm = [u for u in dependabot["updates"] if u["package-ecosystem"] == "npm"]
    assert [u["directory"] for u in npm] == ["/server/frontend"]


def test_unresolved_placeholder_is_detected():
    # The failure this guards is silent: an unsubstituted {{KEY}} written into
    # seven repos renders a config that parses but does nothing useful.
    mod = _renderer()
    assert mod._unresolved(b"directory: {{NPM_DIR}}\n") == ["{{NPM_DIR}}"]
    assert mod._unresolved(b"") == []
    # GitHub Actions expressions share the brace syntax and must not trip it.
    assert mod._unresolved(b"group: codeql-${{ github.ref }}\n") == []
    assert mod._unresolved(b"TOKEN: ${{ secrets.GITHUB_TOKEN }}\n") == []


def test_baseline_workflows_are_valid_and_least_privilege():
    for name in ("codeql.yml", "secret-scan.yml", "pip-audit.yml"):
        doc = yaml.safe_load((_TEMPLATES / "baseline" / name).read_text())
        assert "permissions" in doc, f"{name} must declare a top-level permissions block"
        assert doc["permissions"] == {"contents": "read"}, name
        assert doc["jobs"], name


def test_baseline_actions_are_sha_pinned():
    # A floating tag hands a compromised upstream release whatever token the job
    # holds. Pinning is the whole point of these templates, so assert it rather
    # than trusting review to catch a regression.
    pinned = re.compile(r"^[0-9a-f]{40}$")
    for path in sorted((_TEMPLATES / "baseline").glob("*.yml")):
        for ref in re.findall(r"uses:\s*\S+@(\S+)", path.read_text()):
            assert pinned.match(ref), f"{path.name}: {ref} is not a SHA pin"
