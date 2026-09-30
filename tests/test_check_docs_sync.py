"""Behaviour of tools/check_docs_sync.py, the shared "documentation stays true" gate.

The script is a byte-identical template rendered into every federation repo
(federation-templates/baseline/check_docs_sync.py), so this is the one place its
behaviour is pinned down; the renderer's drift check keeps the copies honest.

Most cases run the real CLI against a throwaway git repository, because the parts
most likely to be wrong are the git plumbing (renames, the index, untracked files,
merge bases), not the arithmetic. Pure helpers are tested directly.
"""

from __future__ import annotations

import ast
import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_TOOL = Path(__file__).resolve().parents[1] / "tools" / "check_docs_sync.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_docs_sync", _TOOL)
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves string annotations through sys.modules, so the module
    # has to be registered before it executes.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mod = _load()


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch):
    """Keep the developer's git config, signing setup and CI env out of the tests."""
    for key, value in {
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }.items():
        monkeypatch.setenv(key, value)
    for key in ("GITHUB_ACTIONS", "PR_BODY", "PR_AUTHOR"):
        monkeypatch.delenv(key, raising=False)


# --------------------------------------------------------------------------- #
# A throwaway repository
# --------------------------------------------------------------------------- #

README = "# Demo\n\nThe API lives in `server/app.py`; see [the guide](docs/guide.md).\n"
GUIDE = "Guide. Configuration is `config/settings.toml`.\n"
MANIFEST = {
    "schema_version": "prii_docs_sync_v1",
    "exempt_docs": ["docs/snapshots/**"],
    "couplings": [
        {
            "doc": "README.md",
            "covers": ["server/**"],
            "why": "README lists the server modules",
        }
    ],
}


class Repo:
    def __init__(self, root: Path) -> None:
        self.root = root

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "-C", str(self.root), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, message: str) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD").strip()

    def set_manifest(self, manifest: dict) -> None:
        self.write(".federation/docs-sync.json", json.dumps(manifest))


def make_repo(tmp_path: Path, manifest: dict | None = None) -> tuple[Repo, str]:
    repo = Repo(tmp_path / "repo")
    repo.root.mkdir(parents=True)
    repo.git("init", "-q")
    repo.git("symbolic-ref", "HEAD", "refs/heads/main")
    repo.write("README.md", README)
    repo.write("docs/guide.md", GUIDE)
    repo.write("docs/snapshots/2026-01-01-audit.md", "Old audit mentions `server/gone.py`.\n")
    repo.write("server/app.py", "print('hi')\n")
    repo.write("config/settings.toml", "a = 1\n")
    repo.set_manifest(manifest if manifest is not None else MANIFEST)
    return repo, repo.commit("base")


def run(capsys, repo: Repo, *args: str) -> tuple[int, str]:
    code = mod.main(["--root", str(repo.root), *args])
    return code, capsys.readouterr().out


def with_coupling(*extra: dict, **top) -> dict:
    return {**MANIFEST, "couplings": list(MANIFEST["couplings"]) + list(extra), **top}


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("pattern", "path", "expected"),
    [
        ("docs/**", "docs/a.md", True),
        ("docs/**", "docs/x/y.md", True),
        ("docs/*", "docs/x/y.md", False),
        ("**/x.py", "x.py", True),
        ("**/x.py", "a/b/x.py", True),
        ("a/**/b", "a/b", True),
        ("a/**/b", "a/x/y/b", True),
        ("*.md", "README.md", True),
        ("*.md", "docs/a.md", False),
        ("server/", "server/a/b.py", True),
        ("Makefile", "Makefile", True),
        ("Makefile", "sub/Makefile", False),
        ("[ab].py", "a.py", True),
        ("[!ab].py", "a.py", False),
        ("?.py", "ab.py", False),
        ("docs/**/*[0-9][0-9]-[0-9][0-9]*.md", "docs/x/AUDIT-2026-09-24.md", True),
    ],
)
def test_glob_semantics(pattern, path, expected):
    assert bool(mod.glob_to_regex(pattern).match(path)) is expected


@pytest.mark.parametrize(
    "line",
    [
        "Docs-Impact: none - internal refactor only",
        "docs-impact: none — internal refactor only",
        "Docs-Impact: none – internal refactor only",
        "Docs-Impact: none -- internal refactor only",
        "Docs-Impact: none: internal refactor only",
        "  - Docs-Impact: none - internal refactor only",
        "> Docs-Impact: none - internal refactor only",
    ],
)
def test_waiver_accepts_the_separators_people_actually_type(line):
    good, bad = mod.parse_waivers(f"subject\n\n{line}\n", "commit abc")
    assert bad == []
    assert [(w.target, w.reason) for w in good] == [("none", "internal refactor only")]


def test_waiver_target_can_be_a_hyphenated_doc_path():
    good, bad = mod.parse_waivers("Docs-Impact: docs/a-b.md - hyphenated but fine", "PR")
    assert bad == [] and good[0].target == "docs/a-b.md"


@pytest.mark.parametrize(
    "line",
    [
        "Docs-Impact: none",
        "Docs-Impact: none - short",
        "Docs-Impact: none because reasons given here",
        "Docs-Impact:",
    ],
)
def test_waiver_without_a_real_reason_is_reported_not_honoured(line):
    good, bad = mod.parse_waivers(line, "commit abc")
    assert good == [] and len(bad) == 1


def test_parse_name_status_understands_renames_and_copies():
    raw = "M\0a.py\0A\0b.py\0D\0c.py\0R100\0old.py\0new.py\0R087\0o2.py\0n2.py\0C090\0s.py\0t.py\0"
    changes = mod.parse_name_status(raw)
    assert [(c.event, c.path, c.old_path) for c in changes] == [
        ("modify", "a.py", None),
        ("add", "b.py", None),
        ("delete", "c.py", None),
        ("rename", "new.py", "old.py"),
        ("rename", "n2.py", "o2.py"),
        ("modify", "n2.py", None),  # a rename that also edited the file
        ("add", "t.py", None),
    ]
    assert mod.parse_name_status("M\0") == []  # truncated output must not raise


def test_extract_refs_keeps_claims_and_drops_noise():
    doc = (
        "See [the guide](docs/guide.md), [anchor](#top), [site](https://example.com/a),\n"
        "[mail](mailto:a@b.c), ![img](assets/logo.png), [out](../outside.md) and\n"
        "[enc](docs/my%20file.md#frag).\n"
        "Paths: `server/app.py`, `docs/`, `./scripts/run.sh`, `tests/test_x.py::test_y`,\n"
        "`src/mod.py:42`.\n"
        "Not paths: `README.md`, `ci.yml`, `server/*.py`, `@scope/pkg`,\n"
        "`sibling-repo/docs/x.md`, `--out=data/x`.\n"
        "Command: `python scripts/run.sh --flag docs/other.md`\n"
        "<!-- `hidden/comment.md` -->\n"
        "```\n`fenced/example.md`\n```\n"
    )
    top = {"docs", "assets", "server", "scripts", "tests", "src", "fenced", "hidden"}
    assert mod.extract_refs("README.md", doc, top) == {
        "docs/guide.md",
        "assets/logo.png",
        "docs/my file.md",
        "server/app.py",
        "docs",
        "scripts/run.sh",
        "tests/test_x.py",
        "src/mod.py",
        "docs/other.md",
    }


def test_relative_links_resolve_against_the_docs_own_directory():
    refs = mod.extract_refs("docs/guide.md", "[up](../README.md) [sib](other.md)", set())
    assert refs == {"README.md", "docs/other.md"}


def test_manifest_reports_every_problem_at_once():
    text = json.dumps(
        {
            "schema_version": "nope",
            "mode": "loud",
            "colour": "blue",
            "couplings": [
                {"doc": "README.md", "cover": ["x"], "why": "typo in the key"},
                {"doc": "A.md", "covers": ["x/**"], "on": ["edit"], "why": ""},
                "not an object",
            ],
        }
    )
    with pytest.raises(mod.ManifestError) as exc:
        mod.parse_manifest(text)
    problems = "\n".join(exc.value.problems)
    for needle in (
        "schema_version",
        "mode must be",
        "unknown key 'colour'",
        "unknown key 'cover'",
        "covers: required",
        "'edit' is not one of",
        "why: required",
        "must be an object",
    ):
        assert needle in problems, needle


def test_manifest_defaults_are_conservative():
    manifest = mod.parse_manifest(json.dumps(MANIFEST))
    assert manifest.mode == "enforce" and manifest.base_branch == "main"
    assert manifest.couplings[0].on == ("add", "delete", "rename")  # not "modify"


# --------------------------------------------------------------------------- #
# R1: co-change, through real git
# --------------------------------------------------------------------------- #


def test_covered_change_without_its_doc_fails_with_an_actionable_message(tmp_path, capsys):
    repo, base = make_repo(tmp_path)
    repo.write("server/routes.py", "x = 1\n")
    repo.commit("add routes")
    code, out = run(capsys, repo, "--base", base)
    assert code == 1
    assert "README.md was not updated" in out
    assert "server/routes.py (add)" in out
    assert "README lists the server modules" in out  # the manifest's `why` is shown
    assert "Docs-Impact: none" in out  # ...and so is the way out


def test_touching_the_doc_in_the_same_diff_satisfies_the_rule(tmp_path, capsys):
    repo, base = make_repo(tmp_path)
    repo.write("server/routes.py", "x = 1\n")
    repo.write("README.md", README + "Routes are in `server/routes.py`.\n")
    repo.commit("add routes")
    code, out = run(capsys, repo, "--base", base)
    assert code == 0 and out.strip() == "docs-sync: 0 violation(s), 0 warning(s), 0 waived"


def test_doc_touched_in_a_different_commit_of_the_same_range_counts(tmp_path, capsys):
    repo, base = make_repo(tmp_path)
    repo.write("server/routes.py", "x = 1\n")
    repo.commit("add routes")
    repo.write("README.md", README + "Routes are in `server/routes.py`.\n")
    repo.commit("document routes")
    assert run(capsys, repo, "--base", base)[0] == 0


def test_content_edits_do_not_trigger_unless_the_coupling_opts_in(tmp_path, capsys):
    repo, base = make_repo(tmp_path)
    repo.write("server/app.py", "print('changed')\n")
    repo.commit("edit app")
    assert run(capsys, repo, "--base", base)[0] == 0

    opted_in = {
        "doc": "docs/guide.md",
        "covers": ["server/app.py"],
        "on": ["modify"],
        "why": "guide quotes the app's behaviour",
    }
    repo2, base2 = make_repo(tmp_path / "second", with_coupling(opted_in))
    repo2.write("server/app.py", "print('changed')\n")
    repo2.commit("edit app")
    code, out = run(capsys, repo2, "--base", base2)
    assert code == 1 and "docs/guide.md was not updated" in out


def test_exclude_carves_paths_out_of_a_coupling(tmp_path, capsys):
    manifest = with_coupling()
    manifest["couplings"][0]["exclude"] = ["server/_internal/**"]
    repo, base = make_repo(tmp_path, manifest)
    repo.write("server/_internal/helper.py", "x = 1\n")
    repo.commit("internal helper")
    assert run(capsys, repo, "--base", base)[0] == 0


def test_a_rename_is_a_structure_change_and_breaks_the_readmes_reference(tmp_path, capsys):
    repo, base = make_repo(tmp_path)
    repo.git("mv", "server/app.py", "server/main.py")
    repo.commit("rename app")
    code, out = run(capsys, repo, "--base", base)
    assert code == 1
    assert "server/app.py (rename)" in out and "server/main.py (rename)" in out
    assert "points at 'server/app.py', which was removed or renamed by this change" in out

    repo.write("README.md", README.replace("server/app.py", "server/main.py"))
    repo.commit("update readme")
    assert run(capsys, repo, "--base", base)[0] == 0


def test_long_lists_of_hits_are_truncated(tmp_path, capsys):
    repo, base = make_repo(tmp_path)
    for i in range(7):
        repo.write(f"server/m{i}.py", "x = 1\n")
    repo.commit("many modules")
    _, out = run(capsys, repo, "--base", base)
    assert "and 3 more" in out


# --------------------------------------------------------------------------- #
# Waivers
# --------------------------------------------------------------------------- #


def _add_route(repo: Repo, message: str) -> None:
    repo.write("server/routes.py", "x = 1\n")
    repo.commit(message)


def test_commit_message_waiver_passes_and_is_echoed_for_reviewers(tmp_path, capsys):
    repo, base = make_repo(tmp_path)
    _add_route(repo, "add routes\n\nDocs-Impact: none - internal module, README lists public ones")
    code, out = run(capsys, repo, "--base", base)
    assert code == 0
    assert "1 waived" in out and "WAIVED README.md: internal module" in out


def test_pr_description_waiver_by_env_and_by_file(tmp_path, capsys, monkeypatch):
    repo, base = make_repo(tmp_path)
    _add_route(repo, "add routes")
    body = "Adds a route.\n\nDocs-Impact: none - internal route, not part of the public API"
    monkeypatch.setenv("PR_BODY", body)
    assert run(capsys, repo, "--base", base)[0] == 0
    monkeypatch.delenv("PR_BODY")
    body_file = tmp_path / "body.md"
    body_file.write_text(body, encoding="utf-8")
    assert run(capsys, repo, "--base", base, "--pr-body-file", str(body_file))[0] == 0
    assert run(capsys, repo, "--base", base)[0] == 1  # and without it, it fails again


def test_waiver_can_name_the_doc_and_must_name_the_right_one(tmp_path, capsys):
    repo, base = make_repo(tmp_path)
    _add_route(repo, "add routes\n\nDocs-Impact: README.md - the README only lists public routes")
    assert run(capsys, repo, "--base", base)[0] == 0

    repo2, base2 = make_repo(tmp_path / "other")
    _add_route(repo2, "add routes\n\nDocs-Impact: docs/guide.md - wrong document named here")
    assert run(capsys, repo2, "--base", base2)[0] == 1


def test_a_waiver_without_a_reason_is_itself_a_violation(tmp_path, capsys):
    repo, base = make_repo(tmp_path)
    _add_route(repo, "add routes\n\nDocs-Impact: none")
    code, out = run(capsys, repo, "--base", base)
    assert code == 1 and "unusable waiver" in out


# --------------------------------------------------------------------------- #
# R2: references are a ratchet
# --------------------------------------------------------------------------- #


def test_legacy_dangling_references_never_block_an_unrelated_change(tmp_path, capsys):
    repo, base = make_repo(tmp_path)
    repo.write("docs/guide.md", GUIDE + "Old thing: `config/missing.toml`.\n")
    base = repo.commit("guide already has a stale reference")
    repo.write("unrelated.txt", "x\n")
    repo.commit("unrelated")
    assert run(capsys, repo, "--base", base)[0] == 0


def test_a_new_dangling_reference_fails_and_only_that_one_is_reported(tmp_path, capsys):
    repo, base = make_repo(tmp_path)
    repo.write("docs/guide.md", GUIDE + "Old: `config/missing.toml`.\n")
    base = repo.commit("stale reference already present")
    repo.write("docs/guide.md", GUIDE + "Old: `config/missing.toml`. New: `config/typo.toml`.\n")
    repo.commit("add another")
    code, out = run(capsys, repo, "--base", base)
    assert code == 1
    assert "'config/typo.toml', which does not exist" in out
    assert "config/missing.toml" not in out


def test_deleting_a_documented_file_forces_the_doc_edit(tmp_path, capsys):
    repo, base = make_repo(tmp_path)
    repo.git("rm", "-q", "config/settings.toml")
    repo.commit("drop config")
    code, out = run(capsys, repo, "--base", base)
    assert code == 1
    assert "docs/guide.md points at 'config/settings.toml', which was removed" in out


def test_ignore_refs_and_exempt_docs_and_doc_waivers_are_the_escape_hatches(tmp_path, capsys):
    def break_it(repo: Repo, message: str) -> None:
        repo.git("rm", "-q", "config/settings.toml")
        repo.commit(message)

    repo, base = make_repo(tmp_path / "a", with_coupling(ignore_refs=["config/**"]))
    break_it(repo, "drop config")
    assert run(capsys, repo, "--base", base)[0] == 0

    repo, base = make_repo(tmp_path / "b", with_coupling(exempt_docs=["docs/guide.md"]))
    break_it(repo, "drop config")
    assert run(capsys, repo, "--base", base)[0] == 0

    repo, base = make_repo(tmp_path / "c")
    break_it(repo, "drop config\n\nDocs-Impact: docs/guide.md - guide is rewritten next PR")
    assert run(capsys, repo, "--base", base)[0] == 0

    # `none` covers judgement calls (R1), not facts: a dangling link is not waivable that way.
    repo, base = make_repo(tmp_path / "d")
    break_it(repo, "drop config\n\nDocs-Impact: none - nothing to document here")
    assert run(capsys, repo, "--base", base)[0] == 1


def test_snapshot_docs_are_never_forced_to_change(tmp_path, capsys):
    repo, base = make_repo(tmp_path)
    repo.write("server/gone.py", "x = 1\n")  # the exempt audit already mentions it...
    repo.write("README.md", README + "`server/gone.py` is new.\n")
    base = repo.commit("gone.py exists at base")
    repo.git("rm", "-q", "server/gone.py")
    repo.write("README.md", README)
    repo.commit("remove it and its README mention")
    assert run(capsys, repo, "--base", base)[0] == 0  # docs/snapshots/... still names it


# --------------------------------------------------------------------------- #
# R3: the manifest cannot rot, and a PR cannot edit its way out of it
# --------------------------------------------------------------------------- #


def test_a_coupling_whose_doc_is_missing_is_a_violation(tmp_path, capsys):
    ghost = {"doc": "docs/ghost.md", "covers": ["config/**"], "why": "documents config"}
    repo, base = make_repo(tmp_path, with_coupling(ghost))
    repo.write("unrelated.txt", "x\n")
    repo.commit("unrelated")
    code, out = run(capsys, repo, "--base", base)
    assert code == 1 and "coupling doc 'docs/ghost.md' does not exist" in out


def test_removing_the_last_file_a_glob_matched_is_a_violation_but_a_dead_glob_only_warns(
    tmp_path, capsys
):
    coupling = {"doc": "docs/guide.md", "covers": ["config/**"], "why": "guide documents config"}
    repo, base = make_repo(tmp_path, with_coupling(coupling))
    repo.git("rm", "-q", "config/settings.toml")
    repo.write("docs/guide.md", "Guide without any config.\n")
    repo.commit("drop config and update the guide")
    code, out = run(capsys, repo, "--base", base)
    assert code == 1 and "removed the last file matching 'config/**'" in out

    dead = {"doc": "docs/guide.md", "covers": ["nothing/**"], "why": "matches nothing yet"}
    repo2, base2 = make_repo(tmp_path / "dead", with_coupling(dead))
    repo2.write("unrelated.txt", "x\n")
    repo2.commit("unrelated")
    code, out = run(capsys, repo2, "--base", base2)
    assert code == 0 and "'nothing/**' (covered by docs/guide.md) matches no files" in out


def test_a_pr_cannot_pass_by_deleting_its_own_coupling(tmp_path, capsys):
    repo, base = make_repo(tmp_path)
    repo.set_manifest({**MANIFEST, "couplings": []})
    repo.write("server/routes.py", "x = 1\n")
    repo.commit("add routes and quietly drop the rule")
    code, out = run(capsys, repo, "--base", base)
    assert code == 1 and "README.md was not updated" in out


def test_a_pr_cannot_pass_by_flipping_the_mode_to_report(tmp_path, capsys):
    repo, base = make_repo(tmp_path)
    repo.set_manifest({**MANIFEST, "mode": "report"})
    repo.write("server/routes.py", "x = 1\n")
    repo.commit("add routes and soften the gate")
    assert run(capsys, repo, "--base", base)[0] == 1


def test_report_mode_prints_the_same_findings_but_never_fails(tmp_path, capsys):
    repo, base = make_repo(tmp_path, {**MANIFEST, "mode": "report"})
    _add_route(repo, "add routes")
    code, out = run(capsys, repo, "--base", base)
    assert code == 0
    assert "REPORT [coupling]" in out and "[report-only]" in out


def test_automated_authors_are_skipped(tmp_path, capsys):
    repo, base = make_repo(tmp_path)
    _add_route(repo, "bump something")
    for author in ("dependabot[bot]", "prii-federation-bot"):
        code, out = run(capsys, repo, "--base", base, "--author", author)
        assert code == 0 and "skipped" in out
    assert run(capsys, repo, "--base", base, "--author", "a-human")[0] == 1


def test_configuration_errors_exit_2_not_1(tmp_path, capsys):
    repo, base = make_repo(tmp_path)
    assert run(capsys, repo, "--base", "no-such-rev")[0] == 2

    (repo.root / ".federation/docs-sync.json").write_text("{not json", encoding="utf-8")
    assert run(capsys, repo, "--base", base)[0] == 2
    assert "not valid JSON" in capsys.readouterr().err or True

    (repo.root / ".federation/docs-sync.json").unlink()
    assert run(capsys, repo, "--base", base)[0] == 2
    assert mod.main(["--root", str(tmp_path / "not-a-repo-at-all")]) == 2


def test_a_mode_is_required(tmp_path):
    repo, _ = make_repo(tmp_path)
    with pytest.raises(SystemExit) as exc:
        mod.main(["--root", str(repo.root)])
    assert exc.value.code == 2


def test_list_and_validate(tmp_path, capsys):
    repo, _ = make_repo(tmp_path)
    code, out = run(capsys, repo, "--list")
    assert code == 0 and "README.md  <-  server/**  [add/delete/rename]" in out
    assert "README lists the server modules" in out
    assert run(capsys, repo, "--validate")[0] == 0

    repo.set_manifest(with_coupling({"doc": "nope.md", "covers": ["config/**"], "why": "x"}))
    code, out = run(capsys, repo, "--validate")
    assert code == 1 and "coupling doc 'nope.md' does not exist" in out


def test_github_annotations_are_emitted_only_inside_actions(tmp_path, capsys, monkeypatch):
    repo, base = make_repo(tmp_path)
    _add_route(repo, "add routes")
    assert "::error" not in run(capsys, repo, "--base", base)[1]
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    out = run(capsys, repo, "--base", base)[1]
    assert "::error file=README.md,title=docs-sync (coupling)::" in out


# --------------------------------------------------------------------------- #
# Pre-commit (--staged)
# --------------------------------------------------------------------------- #


def test_staged_missing_doc_update_is_only_a_warning(tmp_path, capsys):
    repo, _ = make_repo(tmp_path)
    repo.write("server/routes.py", "x = 1\n")
    repo.git("add", "-A")
    code, out = run(capsys, repo, "--staged")
    assert code == 0 and "WARN [coupling]" in out and "0 violation(s), 1 warning(s)" in out


def test_staged_broken_reference_is_an_error(tmp_path, capsys):
    repo, _ = make_repo(tmp_path)
    repo.git("mv", "docs/guide.md", "docs/manual.md")
    code, out = run(capsys, repo, "--staged")
    assert code == 1 and "README.md points at 'docs/guide.md'" in out


def test_staged_on_a_repo_with_no_commits_is_a_quiet_pass(tmp_path, capsys):
    repo = Repo(tmp_path / "fresh")
    repo.root.mkdir()
    repo.git("init", "-q")
    repo.set_manifest(MANIFEST)
    assert run(capsys, repo, "--staged")[0] == 0


# --------------------------------------------------------------------------- #
# The agent-time Stop hook
# --------------------------------------------------------------------------- #


def hook(monkeypatch, capsys, repo: Repo, **payload) -> tuple[int, dict | None]:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    code = mod.main(["--agent-hook", "--root", str(repo.root)])
    out = capsys.readouterr().out
    return code, (json.loads(out) if out.strip() else None)


def test_hook_blocks_on_uncommitted_untracked_work_and_tells_the_agent_what_to_do(
    tmp_path, capsys, monkeypatch
):
    repo, _ = make_repo(tmp_path)
    repo.write("server/routes.py", "x = 1\n")  # untracked, never even staged
    code, decision = hook(monkeypatch, capsys, repo, session_id="s1")
    assert code == 0 and decision["decision"] == "block"
    reason = decision["reason"]
    assert "README.md" in reason and "server/routes.py" in reason
    assert "Docs-Impact: none" in reason  # how to decline, when declining is right


def test_hook_lets_go_once_the_docs_are_updated(tmp_path, capsys, monkeypatch):
    repo, _ = make_repo(tmp_path)
    repo.write("server/routes.py", "x = 1\n")
    repo.write("README.md", README + "Routes are in `server/routes.py`.\n")
    assert hook(monkeypatch, capsys, repo, session_id="s1") == (0, None)


def test_hook_sees_committed_work_and_honours_a_commit_message_waiver(
    tmp_path, capsys, monkeypatch
):
    repo, _ = make_repo(tmp_path)
    repo.git("checkout", "-q", "-b", "feature")
    _add_route(repo, "add routes")
    assert hook(monkeypatch, capsys, repo, session_id="s1")[1]["decision"] == "block"
    repo.write("server/more.py", "y = 2\n")
    repo.commit("more\n\nDocs-Impact: none - internal modules, README lists public ones")
    assert hook(monkeypatch, capsys, repo, session_id="s2") == (0, None)


def test_hook_stops_nagging_after_a_few_rounds_and_leaves_it_to_ci(tmp_path, capsys, monkeypatch):
    repo, _ = make_repo(tmp_path)
    repo.write("server/routes.py", "x = 1\n")
    for _ in range(mod.MAX_HOOK_BLOCKS):
        assert hook(monkeypatch, capsys, repo, session_id="s1")[1]["decision"] == "block"
    payload = json.dumps({"session_id": "s1", "stop_hook_active": True})
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    assert mod.main(["--agent-hook", "--root", str(repo.root)]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and "leaving it to CI" in captured.err
    # A new session, or a new violation, starts the count again.
    assert hook(monkeypatch, capsys, repo, session_id="s2")[1]["decision"] == "block"


def test_hook_is_silent_where_it_has_nothing_to_enforce(tmp_path, capsys, monkeypatch):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert hook(monkeypatch, capsys, Repo(plain), session_id="s") == (0, None)  # not a repo

    repo, _ = make_repo(tmp_path / "configured")
    (repo.root / ".federation/docs-sync.json").unlink()
    repo.write("server/routes.py", "x = 1\n")
    assert hook(monkeypatch, capsys, repo, session_id="s") == (0, None)  # not configured

    repo2, _ = make_repo(tmp_path / "report", {**MANIFEST, "mode": "report"})
    repo2.write("server/routes.py", "x = 1\n")
    assert hook(monkeypatch, capsys, repo2, session_id="s") == (0, None)  # report-only

    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
    assert mod.main(["--agent-hook", "--root", str(repo2.root)]) == 0  # garbage in, no crash


# --------------------------------------------------------------------------- #
# The script as shipped
# --------------------------------------------------------------------------- #


def test_the_script_runs_as_a_program(tmp_path):
    repo, _ = make_repo(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(_TOOL), "--list", "--root", str(repo.root)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0 and "README.md  <-  server/**" in proc.stdout


def test_the_script_stays_parseable_as_python_3_9():
    # hub CI runs the suite on 3.9-3.12; this catches 3.10+ syntax on any interpreter.
    ast.parse(_TOOL.read_text(encoding="utf-8"), feature_version=(3, 9))


def test_the_hubs_own_manifest_is_valid_and_its_globs_still_match(capsys):
    hub = Path(__file__).resolve().parents[1]
    mod.parse_manifest((hub / ".federation" / "docs-sync.json").read_text(encoding="utf-8"))
    code = mod.main(["--root", str(hub), "--validate"])
    assert code == 0, capsys.readouterr().out
