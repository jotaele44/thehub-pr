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


def test_shared_jsx_lint_template_covers_shipped_archive_shells():
    template = (_TEMPLATES / "baseline" / "eslint.config.js").read_text()
    assert '"src/zip-design/**/*.{js,mjs,cjs,jsx}"' in template


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


def test_rendered_launchers_remove_only_successful_setup_logs(tmp_path):
    subprocess.run(
        [sys.executable, str(_RENDER), "--repo", "ovnis-pr", "--repo-root", str(tmp_path)],
        check=True, capture_output=True,
    )
    launchers = (
        tmp_path / "PRII-OVNIS.sh",
        tmp_path / "PRII-OVNIS.command",
        tmp_path / "PRII-OVNIS.app" / "Contents" / "MacOS" / "PRII-OVNIS",
    )
    for launcher in launchers:
        source = launcher.read_text(encoding="utf-8")
        setup = source.index("desktop/setup.py --ensure")
        retained_failure_log = max(source.find("Full log: $LOG"), source.find("Details: $LOG"))
        cleanup = source.index('rm -f "$LOG"')
        launch = source.index("exec .venv/bin/python desktop/launch.py")

        assert setup < retained_failure_log < cleanup < launch, launcher


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
    archive = "https://github.com/jotaele44/thehub-pr/archive/"
    assert f"prii-desktop @ {archive}" in requirements
    assert f"prii-maintenance @ {archive}" in requirements
    assert f"prii-export-utils @ {archive}" in requirements
    assert "git+https://github.com/jotaele44/thehub-pr" not in requirements
    # prii-desktop is pinned to the hub commit that carries the Launch Pad (0.3.0).
    assert f"prii-desktop @ {archive}dc79dc003815432b3f8bfc8f9bff532f6c47e622.zip" in requirements
    assert requirements.count("dc79dc003815432b3f8bfc8f9bff532f6c47e622.zip") == 1
    # The other two must name the same commits as centinelas-pr's pyproject.toml
    # [tool.uv.sources]: an install that reads both files refuses two different
    # URLs for one package.
    maintenance = "f2b81769924689b4d959554928810b1d7b7ef3d6"
    export_utils = "0f62e4bdde10b5ac82787a329d6f15481ab9c7f0"
    assert f"prii-maintenance @ {archive}{maintenance}.zip" in requirements
    assert f"prii-export-utils @ {archive}{export_utils}.zip" in requirements
    assert requirements.count(f"{maintenance}.zip") == 1
    assert requirements.count(f"{export_utils}.zip") == 1


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
    for name in ("codeql.yml", "secret-scan.yml", "pip-audit.yml", "docs-sync.yml"):
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
    # gui/ as well: the hub's Dependabot scans both directories and keeps SHA
    # pins as SHA pins, so a floating tag here would never be bumped to one.
    paths = [*(_TEMPLATES / "baseline").glob("*.y*ml"), *(_TEMPLATES / "gui").glob("*.y*ml")]
    for path in sorted(paths):
        for ref in re.findall(r"uses:\s*\S+@(\S+)", path.read_text()):
            assert pinned.match(ref), f"{path.name}: {ref} is not a SHA pin"


# ── Documentation stays true (docs-sync) ──────────────────────────────────────

_DOCS_SYNC_TARGETS = {
    "baseline/check_docs_sync.py": "tools/check_docs_sync.py",
    "baseline/docs-sync.yml": ".github/workflows/docs-sync.yml",
    "baseline/claude-settings.json": ".claude/settings.json",
    "baseline/CLAUDE.md": "CLAUDE.md",
}


def test_docs_sync_rule_ships_to_every_repo_and_only_as_one_unit():
    # The rule is the checker + its CI job + the agent-time hook + the standing
    # instruction. Shipping a subset (a workflow that calls a script the repo does
    # not have, a hook pointing at nothing) is worse than shipping none, so the
    # four targets must cover exactly the same repos, and all seven of them.
    by_template = {t["template"]: t for t in _targets()}
    everyone = set(_vars())
    for template, output in _DOCS_SYNC_TARGETS.items():
        assert by_template[template]["output"] == output
        assert set(by_template[template]["repos"]) == everyone, template


def test_docs_sync_pieces_agree_with_each_other():
    import json

    workflow = yaml.safe_load((_TEMPLATES / "baseline" / "docs-sync.yml").read_text())
    # PyYAML reads the bare key `on` as the boolean True (YAML 1.1).
    triggers = workflow.get("on", workflow.get(True))
    assert "pull_request" in triggers
    # A required check must report on every PR; a paths filter would leave
    # docs-only PRs waiting on a status that never arrives.
    assert "paths" not in (triggers["pull_request"] or {})
    job = workflow["jobs"]["docs-sync"]
    assert job["name"] == "docs-sync"  # the name to mark as a required status check
    steps = job["steps"]
    assert any(s.get("with", {}).get("fetch-depth") == 0 for s in steps)  # merge base needed
    scripts = "\n".join(s.get("run", "") for s in steps)
    assert "tools/check_docs_sync.py" in scripts
    # PR text is attacker-controlled: it may reach the script only via env.
    assert "github.event" not in scripts

    settings = json.loads((_TEMPLATES / "baseline" / "claude-settings.json").read_text())
    (hook,) = settings["hooks"]["Stop"][0]["hooks"]
    assert hook["type"] == "command"
    assert "tools/check_docs_sync.py" in hook["command"] and "--agent-hook" in hook["command"]

    for name in ("CONTRIBUTING.md", "CLAUDE.md"):
        text = (_TEMPLATES / "baseline" / name).read_text()
        assert ".federation/docs-sync.json" in text, name
        assert "Docs-Impact: none -" in text, name
    pr_template = (_TEMPLATES / "baseline" / "pull_request_template.md").read_text()
    assert "tools/check_docs_sync.py" in pr_template
    precommit = yaml.safe_load((_TEMPLATES / "baseline" / "pre-commit-config.yaml").read_text())
    local = [h for r in precommit["repos"] if r["repo"] == "local" for h in r["hooks"]]
    assert [h["id"] for h in local] == ["docs-sync"]
    assert "tools/check_docs_sync.py --staged" in local[0]["entry"]


def test_docs_sync_files_render_into_a_fresh_repo(tmp_path):
    subprocess.run(
        [sys.executable, str(_RENDER), "--repo", "ovnis-pr", "--repo-root", str(tmp_path)],
        check=True, capture_output=True,
    )
    for output in _DOCS_SYNC_TARGETS.values():
        assert (tmp_path / output).is_file(), output
    # Byte-identical everywhere: the rule must not vary by repo.
    template = (_TEMPLATES / "baseline" / "check_docs_sync.py").read_bytes()
    assert (tmp_path / "tools" / "check_docs_sync.py").read_bytes() == template


def test_pr_grid_v2_runtime_respects_geometry_authority_boundary():
    targets = [
        target
        for target in _targets()
        if target["template"] == "spatial/pr_grid_v2_runtime.py"
    ]
    assert len(targets) == 2

    by_output = {target["output"]: set(target["repos"]) for target in targets}
    assert by_output["federation/spatial/pr_grid_v2_runtime.py"] == {
        "aguayluz-pr",
        "centinelas-pr",
        "moneysweep-pr",
        "ovnis-pr",
        "skywatcher-pr",
    }
    assert by_output["src/hub/grid_v2.py"] == {"thehub-pr"}

    recipients = set().union(*by_output.values())
    assert "spiderweb-pr" not in recipients


# --- GUI rules (ADR 0014, docs/FEDERATION_GUI_STANDARD.md) -------------------

_GUI_RULE_TARGETS = {
    "gui/check_gui_parity.py": "scripts/check_gui_parity.py",
    "gui/test_gui_parity.py": "tests/test_gui_parity.py",
    "gui/GUI_CAPABILITY_PARITY.md": "docs/GUI_CAPABILITY_PARITY.md",
}
_GUI_CODE_TARGETS = {
    "gui/gui-capability-parity.yml": ".github/workflows/gui-capability-parity.yml",
}
_JSX_PRODUCERS = [
    "aguayluz-pr", "centinelas-pr", "moneysweep-pr", "ovnis-pr", "skywatcher-pr",
]


def _gui_targets():
    return {t["template"]: t for t in _targets() if t["template"].startswith("gui/")}


def test_gui_rule_files_ship_as_one_unit():
    """A repo gets the checker, its test and the procedure doc together, or
    none of them: a checker without its doc is an unexplained gate."""
    targets = _gui_targets()
    assert set(targets) == set(_GUI_RULE_TARGETS) | set(_GUI_CODE_TARGETS)
    for template, output in {**_GUI_RULE_TARGETS, **_GUI_CODE_TARGETS}.items():
        assert targets[template]["output"] == output
    rule_sets = {frozenset(targets[t]["repos"]) for t in _GUI_RULE_TARGETS}
    assert len(rule_sets) == 1, rule_sets
    assert "thehub-pr" in next(iter(rule_sets))


def test_gui_workflow_never_reaches_the_two_repos_that_keep_their_own():
    """thehub-pr's e2e mocks its API (no backend step); spiderweb-pr keeps its
    runtime matrix and TypeScript stack. Neither takes the JSX workflow."""
    repos = set(_gui_targets()["gui/gui-capability-parity.yml"]["repos"])
    assert repos <= set(_JSX_PRODUCERS)


def test_gui_code_adopters_have_adopted_the_rules():
    targets = _gui_targets()
    rules = set(targets["gui/check_gui_parity.py"]["repos"])
    code = set(targets["gui/gui-capability-parity.yml"]["repos"])
    assert code <= rules


@pytest.mark.parametrize("program_id", sorted(_vars()))
def test_gui_rule_templates_render_for_every_repo(program_id):
    """Adoption is staged, so most repos are not in the target sets yet. The
    templates must still be renderable for all of them today, or the first
    adoption change discovers a missing variable."""
    mod = _renderer()
    subs = mod._placeholders(_vars()[program_id])
    for template in _GUI_RULE_TARGETS:
        assert mod._unresolved(mod._render_bytes(template, subs)) == [], template


@pytest.mark.parametrize("program_id", _JSX_PRODUCERS)
def test_gui_workflow_renders_valid_and_least_privilege(program_id):
    mod = _renderer()
    vars_ = _vars()[program_id]
    subs = mod._placeholders(vars_)
    raw = mod._render_bytes("gui/gui-capability-parity.yml", subs)
    assert mod._unresolved(raw) == []
    workflow = yaml.safe_load(raw)
    assert workflow["permissions"] == {"contents": "read"}
    e2e = workflow["jobs"]["gui-reachability"]
    assert e2e["defaults"]["run"]["working-directory"] == vars_["frontend_dir"]
    assert (_HUB.parent / program_id).is_dir() is False or (
        _HUB.parent / program_id / vars_["frontend_dir"] / "package.json"
    ).is_file()
    for job in workflow["jobs"].values():
        for step in job["steps"]:
            if "uses" in step:
                assert re.search(r"@[0-9a-f]{40}$", step["uses"]), step["uses"]
    # One entry point: the checker merges fragments itself.
    assert b"check_gui_parity_with_extensions" not in raw


def test_thehub_gui_rule_files_are_the_templates():
    for template, output in _GUI_RULE_TARGETS.items():
        rendered = (_HUB / output).read_bytes()
        if b"{{" in (_TEMPLATES / template).read_bytes():
            continue  # carries per-repo placeholders; covered by --check
        assert rendered == (_TEMPLATES / template).read_bytes(), output


def test_gui_rule_files_render_into_a_fresh_repo(tmp_path):
    subprocess.run(
        [sys.executable, str(_RENDER), "--repo", "thehub-pr", "--repo-root", str(tmp_path)],
        check=True, capture_output=True,
    )
    for output in _GUI_RULE_TARGETS.values():
        assert (tmp_path / output).is_file(), output
    doc = (tmp_path / "docs" / "GUI_CAPABILITY_PARITY.md").read_text()
    assert "thehub-pr follows the federation rule" in doc
    assert "npm --prefix server/frontend run test:gui-parity" in doc


# ── Action pins: Dependabot bumps the template, never a rendered copy ─────────
#
# A pin bumped in a rendered workflow diverges from its template and turns that
# repository's drift gate red (spiderweb-pr#410, fixed by hand in thehub-pr#446).
# So producers exclude their rendered workflows from Dependabot, and the hub's
# Dependabot scans the workflow templates themselves, bumping each template
# together with the hub's own rendered copy. See federation-templates/README.md.

_PRODUCERS = sorted(set(_vars()) - {"thehub-pr"})
_SHA_PIN = re.compile(r"(uses:\s*\S+@)[0-9a-f]{40}")


def _actions_entry(config: dict) -> dict:
    (entry,) = [u for u in config["updates"] if u["package-ecosystem"] == "github-actions"]
    return entry


def _entry(config: dict, ecosystem: str) -> dict:
    (entry,) = [u for u in config["updates"] if u["package-ecosystem"] == ecosystem]
    return entry


def _workflow_targets() -> list[dict]:
    return [t for t in _targets() if t["output"].startswith(".github/workflows/")]


def test_every_repo_gets_exactly_one_dependabot_config():
    configs = [t for t in _targets() if t["output"] == ".github/dependabot.yml"]
    by_template = {t["template"]: t["repos"] for t in configs}
    assert set(by_template) == {"baseline/dependabot.yml", "baseline/dependabot.hub.yml"}
    assert by_template["baseline/dependabot.hub.yml"] == ["thehub-pr"]
    assert sorted(by_template["baseline/dependabot.yml"]) == _PRODUCERS
    # Two templates for one path in the same repo would make the last one win
    # silently, in whatever order targets.yaml happens to list them.
    mod = _renderer()
    seen = set()
    for t in _targets():
        for repo in t["repos"]:
            key = (repo, mod._resolve_output(t["output"], mod._placeholders(_vars()[repo])))
            assert key not in seen, f"{key} is rendered by two templates"
            seen.add(key)


@pytest.mark.parametrize("program_id", sorted(_vars()))
def test_rendered_workflows_are_exactly_the_workflows_rendered(program_id, tmp_path):
    mod = _renderer()
    mod.render_repo(program_id, _vars()[program_id], tmp_path, _targets(), False)
    on_disk = sorted(
        str(p.relative_to(tmp_path))
        for p in (tmp_path / ".github" / "workflows").iterdir()
        if p.suffix in (".yml", ".yaml")
    )
    derived = mod._rendered_workflows(program_id, _targets(), mod._placeholders(_vars()[program_id]))
    assert derived == on_disk
    # template-drift.yml is not rendered (only its PRII_TEMPLATE_REF is
    # managed), so its own actions must stay Dependabot's to bump.
    assert ".github/workflows/template-drift.yml" not in derived
    if program_id == "moneysweep-pr":
        assert ".github/workflows/gui-capability-parity.yml" in derived
        assert ".github/workflows/pip-audit.yml" not in derived


@pytest.mark.parametrize("program_id", _PRODUCERS)
def test_producer_dependabot_never_touches_a_rendered_workflow(program_id, tmp_path):
    mod = _renderer()
    mod.render_repo(program_id, _vars()[program_id], tmp_path, _targets(), False)
    config = yaml.safe_load((tmp_path / ".github" / "dependabot.yml").read_text())
    actions = _actions_entry(config)
    assert actions["directory"] == "/" and "directories" not in actions
    derived = mod._rendered_workflows(program_id, _targets(), mod._placeholders(_vars()[program_id]))
    assert actions["exclude-paths"] == derived
    for rel in actions["exclude-paths"]:
        assert (tmp_path / rel).is_file(), f"{rel} is excluded but not rendered"
    # npm keeps its full scope; pip is narrowed only by the pip-manifest list
    # (test_producer_dependabot_never_touches_a_rendered_pip_manifest).
    assert "exclude-paths" not in _entry(config, "npm")


def test_hub_dependabot_scans_every_workflow_template():
    config = yaml.safe_load((_HUB / ".github" / "dependabot.yml").read_text())
    actions = _actions_entry(config)
    # The hub's own rendered copies must stay in scope: they have to move in the
    # same pull request as their template, or the hub's drift gate goes red.
    assert "exclude-paths" not in actions
    assert "directory" not in actions  # `directories` replaces it
    template_dirs = {
        "/federation-templates/" + str(Path(t["template"]).parent) for t in _workflow_targets()
    }
    assert {"/"} | template_dirs <= set(actions["directories"])


def test_hub_actions_updates_cannot_be_split_across_pull_requests():
    """No group may carry update-types, and every update kind needs a group.

    Ungrouped updates become one pull request per directory. A group limited by
    update-types can split one bump too, because Dependabot judges the semver
    level per directory against the lowest pin it finds there
    (dependency_set.rb combined_version, semver_grouping_rules.rb), and the
    hub's workflows still pin older majors than the templates.
    """
    groups = _actions_entry(yaml.safe_load((_HUB / ".github" / "dependabot.yml").read_text()))["groups"]
    assert groups, "ungrouped updates are split per directory"
    for name, group in groups.items():
        assert "update-types" not in group, name
        assert group.get("patterns") == ["*"], name
    applies_to = sorted(g.get("applies-to", "version-updates") for g in groups.values())
    assert applies_to == ["security-updates", "version-updates"]


def test_scanned_template_directories_hold_only_parseable_yaml():
    # Dependabot parses every *.yml / *.yaml directly inside a scanned directory
    # as a workflow; one that does not parse fails the whole actions update.
    actions = _actions_entry(yaml.safe_load((_HUB / ".github" / "dependabot.yml").read_text()))
    for directory in actions["directories"]:
        if directory == "/":
            continue
        files = [p for p in sorted((_HUB / directory.lstrip("/")).iterdir())
                 if p.is_file() and p.suffix in (".yml", ".yaml")]
        assert files, directory
        for path in files:
            yaml.safe_load(path.read_bytes().decode("utf-8"))


def test_both_dependabot_templates_agree_outside_the_actions_scope():
    producer = yaml.safe_load((_TEMPLATES / "baseline" / "dependabot.yml").read_text())
    hub = yaml.safe_load((_TEMPLATES / "baseline" / "dependabot.hub.yml").read_text())
    assert _entry(producer, "npm") == _entry(hub, "npm")
    # Producers exclude their rendered pip manifests; the hub excludes nothing,
    # because its scan has to keep reaching the requirements templates.
    producer_pip = dict(_entry(producer, "pip"))
    assert producer_pip.pop("exclude-paths") == ["{{RENDERED_PIP_MANIFESTS}}"]
    assert producer_pip == _entry(hub, "pip")
    for key in ("schedule", "open-pull-requests-limit", "labels", "commit-message"):
        assert _actions_entry(producer)[key] == _actions_entry(hub)[key], key


@pytest.mark.parametrize("key", [
    "rendered_workflows", "RENDERED_WORKFLOWS",
    "rendered_pip_manifests", "RENDERED_PIP_MANIFESTS",
])
def test_a_var_cannot_shadow_the_derived_placeholder(key):
    mod = _renderer()
    vars_ = {**_vars()["ovnis-pr"], key: "nothing"}
    with pytest.raises(SystemExit, match=key.upper()):
        mod._subs_for("ovnis-pr", vars_, _targets())


def test_an_empty_derived_list_drops_only_its_line(tmp_path):
    # Rendering `exclude-paths: [""]` would hand Dependabot a pattern that
    # matches nothing while looking deliberate. Nothing to exclude means no key:
    # rendered alone, the config gives ovnis-pr no workflow and no pip manifest,
    # so both exclude-paths lines go and nothing else does.
    mod = _renderer()
    only_config = [{"template": "baseline/dependabot.yml",
                    "output": ".github/dependabot.yml", "repos": ["ovnis-pr"]}]
    subs, empty = mod._subs_for("ovnis-pr", _vars()["ovnis-pr"], only_config)
    assert empty == {"{{RENDERED_WORKFLOWS}}", "{{RENDERED_PIP_MANIFESTS}}"}
    assert not set(subs) & empty
    mod.render_repo("ovnis-pr", _vars()["ovnis-pr"], tmp_path, only_config, False)
    # The template with every other placeholder filled in, before any line drop.
    template = mod._render_bytes("baseline/dependabot.yml", subs).decode().splitlines()
    rendered = (tmp_path / ".github" / "dependabot.yml").read_text().splitlines()
    assert [line for line in template if line not in rendered] == [
        '    exclude-paths: ["{{RENDERED_PIP_MANIFESTS}}"]',
        '    exclude-paths: ["{{RENDERED_WORKFLOWS}}"]',
    ]
    assert len(rendered) == len(template) - 2
    config = yaml.safe_load("\n".join(rendered))
    assert all("exclude-paths" not in u for u in config["updates"])


@pytest.mark.parametrize("line", [
    'exclude-paths: ["{{RENDERED_PIP_MANIFESTS}}", "extra.txt"]',
    'exclude-paths: [{{RENDERED_PIP_MANIFESTS}}]',
    'exclude-paths: ["{{RENDERED_PIP_MANIFESTS}}"]  # trailing comment',
    'note: "{{RENDERED_PIP_MANIFESTS}}"',
])
def test_an_empty_derived_list_anywhere_else_is_refused(tmp_path, monkeypatch, line):
    # Only a whole `<key>: ["{{P}}"]` line can be omitted. Anything else would
    # have to be rewritten rather than dropped, so the render refuses it.
    mod = _renderer()
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "x.yml").write_text(f"a: 1\n{line}\nb: 2\n")
    monkeypatch.setattr(mod, "_TEMPLATES", templates)
    targets = [{"template": "x.yml", "output": "x.yml", "repos": ["spiderweb-pr"]}]
    with pytest.raises(SystemExit, match=r"RENDERED_PIP_MANIFESTS.*empty for this repo"):
        mod.render_repo("spiderweb-pr", _vars()["spiderweb-pr"], tmp_path / "out", targets, True)


def _bump_every_pin(path: Path) -> None:
    """Rewrite each SHA pin the way a Dependabot version update does."""
    text = path.read_text()
    bumped = _SHA_PIN.sub(r"\g<1>" + "f" * 40, text)
    assert bumped != text, path
    path.write_text(bumped)


def test_a_dependabot_bump_of_template_and_hub_copy_keeps_the_hub_green(tmp_path, monkeypatch):
    """The mechanism end to end, minus Dependabot: one pull request that edits a
    template and the hub's copy identically leaves the hub's drift gate green,
    while either edit alone is drift. That holds only while no `uses:` line in a
    workflow template carries a placeholder, so that is asserted as well."""
    import shutil

    mod = _renderer()
    templates = tmp_path / "federation-templates"
    shutil.copytree(_TEMPLATES, templates)
    monkeypatch.setattr(mod, "_TEMPLATES", templates)
    hub_targets = [t for t in _workflow_targets() if "thehub-pr" in t["repos"]]
    assert hub_targets
    for t in _workflow_targets():
        for line in (templates / t["template"]).read_text().splitlines():
            if line.lstrip().startswith(("uses:", "- uses:")):
                assert "{{" not in line, f"{t['template']}: {line.strip()}"

    def fresh_hub(name: str) -> Path:
        root = tmp_path / name
        mod.render_repo("thehub-pr", _vars()["thehub-pr"], root, _targets(), False)
        return root

    def check(root: Path) -> list[str]:
        return mod.render_repo("thehub-pr", _vars()["thehub-pr"], root, _targets(), True)

    copy_only = fresh_hub("copy-only")
    _bump_every_pin(copy_only / ".github/workflows/codeql.yml")
    assert check(copy_only) == [".github/workflows/codeql.yml"]

    together = fresh_hub("together")
    for t in hub_targets:
        _bump_every_pin(templates / t["template"])
        _bump_every_pin(together / t["output"])
    assert check(together) == []

    # copy-only was rendered from the old templates, so after the template bump
    # its unbumped files are now the drift: a template-only change is caught.
    template_only = sorted(t["output"] for t in hub_targets if t["output"] != ".github/workflows/codeql.yml")
    assert sorted(check(copy_only)) == template_only


# ── Pip manifests: the same rule for requirements-desktop.txt ─────────────────
#
# A requirement bumped in a rendered pip manifest (pywebview in the desktop
# producers' requirements-desktop.txt) diverges from its template and fails that
# repository's drift gate, exactly like an action pin. Producers exclude their
# rendered manifests from the pip ecosystem; the hub's pip scan of "/" reaches
# the template one directory down and bumps it together with the hub's own
# requirements-desktop.txt (as dependabot[bot] did in f1cfad5). See
# federation-templates/README.md and ADR 0016.

_DESKTOP_REQUIREMENTS = "requirements-desktop.txt"


def _pip_manifest_targets() -> list[dict]:
    """Targets whose output some repo's {{RENDERED_PIP_MANIFESTS}} lists."""
    mod = _renderer()
    listed = set()
    for program_id, vars_ in _vars().items():
        listed |= {(program_id, rel) for rel in
                   mod._rendered_pip_manifests(program_id, _targets(), mod._placeholders(vars_))}
    return [t for t in _targets()
            if any((repo, mod._resolve_output(t["output"], mod._placeholders(_vars()[repo])))
                   in listed for repo in t["repos"])]


def _pywebview_line(path: Path) -> str:
    (line,) = [ln for ln in path.read_text().splitlines()
               if re.match(r"pywebview\b", ln.strip())]
    return line.strip()


def test_pip_manifests_follow_dependabots_pip_scan():
    # dependabot-core python shared_file_fetcher.rb: *.txt / *.in at the root
    # and one directory below (req_txt_and_in_files, req_files_for_dir), plus
    # fixed manifest names at the root only.
    mod = _renderer()
    outputs = [
        "requirements-desktop.txt", "constraints.txt", "deps.in", "pyproject.toml",
        "setup.py", "Pipfile.lock", "requirements/dev.txt", ".github/extra.txt",
        "a/b/deep.txt", "sub/pyproject.toml", "README.md", "LICENSE",
        ".github/workflows/codeql.yml", "PRII-{{APP_SLUG}}.sh",
    ]
    targets = [{"template": "unused", "output": o, "repos": ["ovnis-pr"]} for o in outputs]
    assert mod._rendered_pip_manifests("ovnis-pr", targets, mod._placeholders(_vars()["ovnis-pr"])) == sorted([
        "requirements-desktop.txt", "constraints.txt", "deps.in", "pyproject.toml",
        "setup.py", "Pipfile.lock", "requirements/dev.txt", ".github/extra.txt",
    ])


def test_a_pip_manifest_path_that_needs_quoting_is_refused():
    mod = _renderer()
    targets = [{"template": "unused", "output": "requirements desktop.txt", "repos": ["ovnis-pr"]}]
    with pytest.raises(SystemExit, match="pip manifest path"):
        mod._rendered_pip_manifests("ovnis-pr", targets, {})


@pytest.mark.parametrize("program_id", sorted(_vars()))
def test_rendered_pip_manifests_per_repo(program_id, tmp_path):
    mod = _renderer()
    (desktop,) = [t for t in _targets() if t["output"] == _DESKTOP_REQUIREMENTS]
    derived = mod._rendered_pip_manifests(program_id, _targets(), mod._placeholders(_vars()[program_id]))
    expected = [_DESKTOP_REQUIREMENTS] if program_id in desktop["repos"] else []
    assert derived == expected
    if program_id in ("aguayluz-pr", "centinelas-pr", "moneysweep-pr", "ovnis-pr", "skywatcher-pr"):
        assert derived == [_DESKTOP_REQUIREMENTS]
    if program_id in ("spiderweb-pr", "thehub-pr"):
        # Both keep their own requirements-desktop.txt, so it stays Dependabot's.
        assert derived == []
    mod.render_repo(program_id, _vars()[program_id], tmp_path, _targets(), False)
    for rel in derived:
        assert (tmp_path / rel).is_file(), f"{rel} is listed but not rendered"


@pytest.mark.parametrize("program_id", _PRODUCERS)
def test_producer_dependabot_never_touches_a_rendered_pip_manifest(program_id, tmp_path):
    mod = _renderer()
    mod.render_repo(program_id, _vars()[program_id], tmp_path, _targets(), False)
    config = yaml.safe_load((tmp_path / ".github" / "dependabot.yml").read_text())
    pip = _entry(config, "pip")
    assert pip["directory"] == "/" and "directories" not in pip
    derived = mod._rendered_pip_manifests(program_id, _targets(), mod._placeholders(_vars()[program_id]))
    if derived:
        assert pip["exclude-paths"] == derived
    else:
        # spiderweb-pr renders no pip manifest: no key, not an empty pattern.
        assert "exclude-paths" not in pip
    assert "exclude-paths" not in _entry(config, "npm")


def test_hub_pip_scan_reaches_every_pip_manifest_template():
    # The hub's pip ecosystem bumps the templates only because "/" reaches one
    # directory down. A pip manifest template moved deeper (baseline/, say)
    # would silently stop being bumped; a second directory or an exclude-paths
    # entry would split or drop the bump.
    config = yaml.safe_load((_HUB / ".github" / "dependabot.yml").read_text())
    pip = _entry(config, "pip")
    assert pip["directory"] == "/"
    assert "directories" not in pip and "exclude-paths" not in pip
    templates = _pip_manifest_targets()
    assert [t["template"] for t in templates] == [_DESKTOP_REQUIREMENTS]
    for t in templates:
        rel = Path("federation-templates") / t["template"]
        assert len(rel.parts) <= 2 and rel.suffix in (".txt", ".in"), rel


def test_pip_manifest_templates_keep_placeholders_off_requirement_lines():
    # Dependabot edits a registry requirement line in the template and in the
    # hub's copy alike, so that line must read the same in both: no placeholder.
    # A direct reference (`name @ url`) is parsed but never bumped, so a
    # placeholder may trail it, as {{DESKTOP_EXTRA_REQUIREMENTS}} does.
    for t in _pip_manifest_targets():
        for line in (_TEMPLATES / t["template"]).read_text().splitlines():
            stripped = line.strip()
            if "{{" in stripped and not stripped.startswith("#"):
                assert " @ " in stripped, f"{t['template']}: {stripped}"


def test_template_pywebview_floor_matches_the_hubs_own():
    # The hub's Dependabot bumps both lines in one pull request (f1cfad5). Equal
    # lines keep the hub testing the floor that producers ship, and a hand edit
    # to only one of them fails here.
    assert _pywebview_line(_TEMPLATES / _DESKTOP_REQUIREMENTS) == _pywebview_line(_HUB / _DESKTOP_REQUIREMENTS)


def test_a_pywebview_bump_in_the_template_reaches_producers_only_by_sync(tmp_path, monkeypatch):
    """The hub stays green and a producer's next sync carries the bump."""
    import shutil

    mod = _renderer()
    producer = tmp_path / "centinelas-pr"
    mod.render_repo("centinelas-pr", _vars()["centinelas-pr"], producer, _targets(), False)
    assert mod.render_repo("centinelas-pr", _vars()["centinelas-pr"], producer, _targets(), True) == []

    templates = tmp_path / "federation-templates"
    shutil.copytree(_TEMPLATES, templates)
    monkeypatch.setattr(mod, "_TEMPLATES", templates)
    template = templates / _DESKTOP_REQUIREMENTS
    text = template.read_text()
    old = _pywebview_line(template)
    template.write_text(text.replace(old, "pywebview>=99.0", 1))

    hub = tmp_path / "thehub-pr"
    mod.render_repo("thehub-pr", _vars()["thehub-pr"], hub, _targets(), False)
    assert mod.render_repo("thehub-pr", _vars()["thehub-pr"], hub, _targets(), True) == []
    assert mod.render_repo("centinelas-pr", _vars()["centinelas-pr"], producer, _targets(), True) == [_DESKTOP_REQUIREMENTS]
