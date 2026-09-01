"""Tests for the federation boilerplate renderer (tools/render_federation_templates.py).

Runs in thehub CI where the producer sibling checkouts are absent, so these cover
the renderer logic + manifest integrity + thehub's own committed files (thehub is
checked out). The cross-repo byte-equality is enforced in each producer by its
template-drift.yml workflow.
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
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


def test_spiderweb_keeps_enriched_shell_launchers_repo_owned():
    managed = {t["template"] for t in _targets() if "spiderweb-pr" in t["repos"]}
    assert "PRII-APP.command" not in managed
    assert "PRII-APP.sh" not in managed
    assert "PRII-APP.app/Contents/MacOS/PRII-APP" not in managed
    assert "PRII-APP.bat" in managed


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


def test_rendered_templates_do_not_require_hub_sibling_paths(tmp_path):
    subprocess.run(
        [sys.executable, str(_RENDER), "--repo", "ovnis-pr", "--repo-root", str(tmp_path)],
        check=True, capture_output=True,
    )
    rendered_text = "\n".join(path.read_text() for path in tmp_path.rglob("*") if path.is_file())
    assert "../thehub-pr" not in rendered_text


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


def _write_template_drift_workflow(root: Path, template_ref: str) -> Path:
    path = root / ".github" / "workflows" / "template-drift.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "name: Federation template drift\n"
        "jobs:\n"
        "  drift:\n"
        "    env:\n"
        f"      PRII_TEMPLATE_REF: {template_ref}\n"
        "    steps:\n"
        "      - uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065\n",
        encoding="utf-8",
    )
    return path


def test_template_ref_write_and_check_preserve_unrelated_workflow_bytes(tmp_path):
    old_ref = "1" * 40
    new_ref = "2" * 40
    workflow = _write_template_drift_workflow(tmp_path, old_ref)
    before = workflow.read_bytes()
    mod = _renderer()

    assert mod._manage_template_ref(tmp_path, new_ref, check=False)
    after = workflow.read_bytes()
    assert after == before.replace(old_ref.encode(), new_ref.encode())
    assert mod._manage_template_ref(tmp_path, new_ref, check=True) is False
    assert mod._manage_template_ref(tmp_path, old_ref, check=True) is True


def test_template_ref_cli_reports_then_closes_binding_drift(tmp_path):
    old_ref = "1" * 40
    new_ref = "2" * 40
    subprocess.run(
        [sys.executable, str(_RENDER), "--repo", "ovnis-pr", "--repo-root", str(tmp_path)],
        check=True,
    )
    _write_template_drift_workflow(tmp_path, old_ref)
    command = [
        sys.executable, str(_RENDER), "--repo", "ovnis-pr",
        "--repo-root", str(tmp_path), "--template-ref", new_ref,
    ]

    drift = subprocess.run([*command, "--check"], capture_output=True, text=True)
    assert drift.returncode == 1
    assert str(_renderer()._TEMPLATE_REF_PATH) in drift.stdout
    subprocess.run(command, check=True)
    assert subprocess.run([*command, "--check"]).returncode == 0


@pytest.mark.parametrize("template_ref", ["main", "A" * 40, "a" * 39, "a" * 41])
def test_template_ref_rejects_every_noncanonical_sha(tmp_path, template_ref):
    _write_template_drift_workflow(tmp_path, "1" * 40)
    with pytest.raises(SystemExit, match="lowercase 40-character Git SHA"):
        _renderer()._manage_template_ref(tmp_path, template_ref, check=False)


def test_template_ref_requires_one_semantically_bound_scalar(tmp_path):
    workflow = _write_template_drift_workflow(tmp_path, "1" * 40)
    scalar = f"      PRII_TEMPLATE_REF: {'1' * 40}"
    workflow.write_text(
        workflow.read_text(encoding="utf-8").replace(scalar, f"{scalar}\n{scalar}"),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="expected exactly one"):
        _renderer()._manage_template_ref(tmp_path, "2" * 40, check=False)


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


def test_centinelas_desktop_requirements_support_plain_pip_install(tmp_path):
    subprocess.run(
        [sys.executable, str(_RENDER), "--repo", "centinelas-pr", "--repo-root", str(tmp_path)],
        check=True, capture_output=True,
    )
    requirements = (tmp_path / "requirements-desktop.txt").read_text(encoding="utf-8")
    assert "prii-desktop @ git+https://github.com/jotaele44/thehub-pr.git@" in requirements
    assert "prii-maintenance @ git+https://github.com/jotaele44/thehub-pr.git@" in requirements
    assert "prii-export-utils @ git+https://github.com/jotaele44/thehub-pr.git@" in requirements


def test_every_producer_declares_an_app_title():
    # app_title cannot be derived from app_slug: OVNIS stays upper-case while the
    # rest are title-case, and AguaYLuz/MoneySweep/TheHub carry internal capitals,
    # so any casing rule would corrupt four of seven repos' user-visible branding.
    for repo, v in _vars().items():
        assert v.get("app_title"), f"{repo} has no app_title"
        assert v["app_title"] != v["app_slug"].title(), (
            f"{repo}: app_title looks derived from the slug; it must be the real name"
        )


def test_app_bundle_launcher_is_shared_and_guards_translocation(tmp_path):
    # The whole point of templating this file: the App Translocation fix landed in
    # one repo and left the others broken, because every repo carried its own copy.
    subprocess.run(
        [sys.executable, str(_RENDER), "--repo", "ovnis-pr", "--repo-root", str(tmp_path)],
        check=True, capture_output=True,
    )
    launcher = tmp_path / "PRII-OVNIS.app/Contents/MacOS/PRII-OVNIS"
    assert launcher.stat().st_mode & 0o100, "bundle executable must be owner-executable"
    text = launcher.read_text(encoding="utf-8")
    assert "AppTranslocation" in text, "translocation guard missing from the shared launcher"
    assert 'with title \\"OVNIS — PRII\\"' in text
    assert "{{" not in text, "unsubstituted placeholder survived"


def test_mode_falls_back_to_the_extension_contract():
    # The implicit rule the launchers have always relied on.
    mod = _renderer()
    assert mod._mode_for("PRII-OVNIS.sh", {}) == 0o755
    assert mod._mode_for("PRII-OVNIS.command", {}) == 0o755
    assert mod._mode_for("SECURITY.md", {}) is None


def test_declared_mode_accepts_both_yaml_spellings():
    # YAML 1.1 resolves an unquoted 0755 to the int 493, so a renderer that
    # always parsed base 8 would raise on the digit 9 and take rendering down
    # the moment anyone wrote the mode the natural way.
    mod = _renderer()
    assert yaml.safe_load("mode: 0755\n")["mode"] == 493  # documents the trap
    assert mod._mode_for("x", {"mode": 0o755}) == 0o755
    assert mod._mode_for("x", {"mode": "0755"}) == 0o755
    assert mod._mode_for("x", {"mode": 0o644}) == 0o644


def test_implausible_mode_is_rejected_with_a_usable_message():
    mod = _renderer()
    try:
        mod._mode_for("PRII-OVNIS.app/Contents/MacOS/PRII-OVNIS", {"mode": 0o10000})
    except SystemExit as exc:
        assert "permission mask" in str(exc)
    else:
        raise AssertionError("expected SystemExit")


def test_check_requires_the_owner_execute_bit(tmp_path):
    # A file left group/other-executable only cannot be run by the owner, so
    # accepting "any exec bit" would report a broken launcher as matching.
    # 0700 must still pass: that is what a umask 077 checkout legitimately gives.
    mod = _renderer()
    rel = "PRII-OVNIS.app/Contents/MacOS/PRII-OVNIS"
    target = {
        "template": "PRII-APP.command",
        "output": "PRII-{{APP_SLUG}}.app/Contents/MacOS/PRII-{{APP_SLUG}}",
        "repos": ["ovnis-pr"],
        "mode": 0o755,
    }
    mod.render_repo("ovnis-pr", _vars()["ovnis-pr"], tmp_path, [target], False)
    dest = tmp_path / rel

    # Owner keeps read (--check has to read the file to compare it) but loses
    # exec, while group and other keep theirs.
    dest.chmod(0o455)
    assert mod.render_repo("ovnis-pr", _vars()["ovnis-pr"], tmp_path, [target], True) == [rel]

    dest.chmod(0o700)  # umask 077 checkout — owner can run it, not drift
    assert mod.render_repo("ovnis-pr", _vars()["ovnis-pr"], tmp_path, [target], True) == []


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


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses permission bits")
def test_unreadable_file_is_drift_not_a_crash(tmp_path):
    # --check has to read a file to compare it. If it cannot, the honest answer
    # is drift: letting the OSError propagate would abandon the report for every
    # later file, and under --all every later repo.
    mod = _renderer()
    subprocess.run(
        [sys.executable, str(_RENDER), "--repo", "ovnis-pr", "--repo-root", str(tmp_path)],
        check=True, capture_output=True,
    )
    launcher = tmp_path / "PRII-OVNIS.sh"
    launcher.chmod(0o000)
    try:
        drift = mod.render_repo("ovnis-pr", _vars()["ovnis-pr"], tmp_path, _targets(), True)
    finally:
        launcher.chmod(0o644)  # so tmp_path cleanup can remove it
    assert "PRII-OVNIS.sh" in drift


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
