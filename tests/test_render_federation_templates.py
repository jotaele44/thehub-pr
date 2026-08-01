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


def test_mode_falls_back_to_the_extension_contract():
    # The implicit rule the launchers have always relied on.
    mod = _renderer()
    assert mod._mode_for("PRII-OVNIS.sh", {}) == 0o755
    assert mod._mode_for("PRII-OVNIS.command", {}) == 0o755
    assert mod._mode_for("SECURITY.md", {}) is None


def test_declared_mode_covers_outputs_the_extension_rule_cannot_see(tmp_path):
    # An executable inside a macOS .app bundle has no suffix, so the extension
    # rule leaves it 0644 on a first render and --check cannot tell that the app
    # is broken, because the content still matches. A declared mode fixes both
    # halves; this exercises them against a synthetic target.
    mod = _renderer()
    rel = "PRII-OVNIS.app/Contents/MacOS/PRII-OVNIS"
    target = {
        "template": "PRII-APP.command",
        "output": "PRII-{{APP_SLUG}}.app/Contents/MacOS/PRII-{{APP_SLUG}}",
        "repos": ["ovnis-pr"],
        "mode": "0755",
    }
    assert mod._mode_for(target["output"], target) == 0o755

    # First render into a tree where the file does not exist yet.
    assert mod.render_repo("ovnis-pr", _vars()["ovnis-pr"], tmp_path, [target], False) == []
    dest = tmp_path / rel
    assert dest.stat().st_mode & 0o111, "bundle executable rendered non-executable"
    assert mod.render_repo("ovnis-pr", _vars()["ovnis-pr"], tmp_path, [target], True) == []

    # Content untouched, exec bit dropped — must be reported as drift.
    dest.chmod(0o644)
    assert mod.render_repo("ovnis-pr", _vars()["ovnis-pr"], tmp_path, [target], True) == [rel]


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


def test_governance_files_never_name_another_repo(tmp_path):
    # Substitution is plain string replacement, so the way this breaks is not a
    # missing var (that already raises) but a *wrong* one — a governance file
    # rendered into ovnis-pr that points at moneysweep-pr's security advisory
    # page would look completely normal and quietly route reports to the wrong
    # repository.
    # Checked on the GitHub URLs specifically, not on any mention of a sibling:
    # these files legitimately cite thehub-pr/federation-templates/ as the place
    # the template lives. It is the *links* that must be self-referential.
    subprocess.run(
        [sys.executable, str(_RENDER), "--repo", "ovnis-pr", "--repo-root", str(tmp_path)],
        check=True, capture_output=True,
    )
    url = re.compile(r"github\.com/jotaele44/([a-z-]+-pr)")
    # Files carrying absolute links: every one must point at this repo.
    for rel in ("SECURITY.md", ".github/ISSUE_TEMPLATE/config.yml"):
        path = tmp_path / rel
        assert path.is_file(), rel
        linked = set(url.findall(path.read_text()))
        assert linked, f"{rel} links to no repo at all"
        assert linked == {"ovnis-pr"}, f"{rel} links to {sorted(linked)}, not just ovnis-pr"

    # CONTRIBUTING.md deliberately uses relative links for in-repo files, so it
    # carries no absolute URLs — check the identity it states in prose instead.
    contributing = (tmp_path / "CONTRIBUTING.md").read_text()
    assert not url.findall(contributing), "CONTRIBUTING.md should use relative in-repo links"
    assert "# Contributing to ovnis-pr" in contributing


def test_baseline_actions_are_sha_pinned():
    # A floating tag hands a compromised upstream release whatever token the job
    # holds. Pinning is the whole point of these templates, so assert it rather
    # than trusting review to catch a regression.
    pinned = re.compile(r"^[0-9a-f]{40}$")
    for path in sorted((_TEMPLATES / "baseline").glob("*.yml")):
        for ref in re.findall(r"uses:\s*\S+@(\S+)", path.read_text()):
            assert pinned.match(ref), f"{path.name}: {ref} is not a SHA pin"
