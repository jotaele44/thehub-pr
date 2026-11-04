"""Exercise the actual fixture publisher Bash with isolated GitHub/Git stubs."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import textwrap

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/federation-ingest.yml"
STEP = "      - name: Open fixture-refresh review PR with governed publisher"


def _script() -> str:
    content = WORKFLOW.read_text(encoding="utf-8")
    assert content.count(STEP) == 1
    raw = content.split(STEP, 1)[1].split("        run: |\n", 1)[1]
    raw = raw.split("\n      - name: Note that the fixture was already current", 1)[0]
    return textwrap.dedent(raw)


def _run(tmp_path: Path, configured: bool, login: str = "", push: str = "", *, git_ok: bool = False, pr_ok: bool = False):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    trace = tmp_path / "calls.txt"
    git = bin_dir / "git"
    git.write_text('#!/bin/sh\nprintf "git %s\\n" "$*" >> "$TRACE"\nif [ "$GIT_OK" = true ]; then\n  if [ "$1" = rev-parse ]; then echo fake-commit-sha; fi\n  exit 0\nfi\nexit 81\n')
    git.chmod(0o755)
    gh = bin_dir / "gh"
    gh.write_text(
        '#!/bin/sh\nprintf "gh %s\\n" "$*" >> "$TRACE"\n'
        'if [ "$1" = api ] && [ "$2" = user ]; then\n'
        '  if [ -z "$LOGIN" ]; then exit 72; fi\n'
        '  printf "%s\\n" "$LOGIN"; exit 0\n'
        'fi\n'
        'if [ "$1" = api ] && [ "$2" = "repos/$GITHUB_REPOSITORY" ]; then\n'
        '  printf "%s\\n" "$PUSH"; exit 0\n'
        'fi\n'
        'if [ "$1" = pr ] && [ "$2" = create ]; then\n'
        '  if [ "$PR_OK" = true ]; then exit 0; fi\n'
        '  exit 73\n'
        'fi\n'
        'if [ "$1" = api ] && [ "$2" = --silent ] && [ "$3" = -X ] && [ "$4" = POST ] && [ "$5" = "repos/$GITHUB_REPOSITORY/statuses/fake-commit-sha" ]; then exit 0; fi\n'
        'exit 73\n'
    )
    gh.chmod(0o755)
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "check_docs_sync.py").write_text("raise SystemExit(0)\n")
    env = dict(os.environ)
    env.update({
        "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
        "HAS_SYNC_PAT": "true" if configured else "false",
        "LOGIN": login,
        "PUSH": push,
        "GIT_OK": "true" if git_ok else "false",
        "PR_OK": "true" if pr_ok else "false",
        "STATUS_TOKEN": "stub-status-token",
        "GITHUB_SHA": "fake-base-sha",
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_WORKFLOW": "Federation ingest",
        "TRACE": str(trace),
        "GITHUB_REPOSITORY": "example/thehub-pr",
        "GITHUB_RUN_ID": "987654",
        "GITHUB_RUN_ATTEMPT": "2",
    })
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", _script()],
        cwd=tmp_path, env=env, text=True, capture_output=True, check=False,
    )
    return result, trace.read_text() if trace.exists() else ""


def test_missing_secret_has_no_external_actions(tmp_path: Path) -> None:
    result, calls = _run(tmp_path, False)
    assert result.returncode != 0
    assert calls == ""
    assert "SYNC_PAT is absent" in result.stdout


def test_invalid_token_cannot_write(tmp_path: Path) -> None:
    result, calls = _run(tmp_path, True)
    assert result.returncode != 0
    assert "gh api user" in calls
    assert "git " not in calls


def test_bot_publisher_cannot_write(tmp_path: Path) -> None:
    result, calls = _run(tmp_path, True, "github-actions[bot]", "true")
    assert result.returncode != 0
    assert "git " not in calls


def test_insufficient_push_rights_cannot_write(tmp_path: Path) -> None:
    result, calls = _run(tmp_path, True, "publisher", "false")
    assert result.returncode != 0
    assert "git " not in calls


def test_unique_branch_and_no_force_push() -> None:
    content = _script()
    assert 'branch="fixture-refresh/' in content
    assert "GITHUB_RUN_ID" in content and "GITHUB_RUN_ATTEMPT" in content
    assert "git push --force" not in content
    assert 'git push origin "HEAD:refs/heads/$branch"' in content
    assert "gh pr create --draft" in content
    assert "gh pr edit" not in content
    assert content.index('can_push="$(gh api') < content.index("git checkout -b")
    assert content.index("git checkout -b") < content.index('git push origin "HEAD:refs/heads/$branch"')
    assert "always()" in WORKFLOW.read_text(encoding="utf-8")


def test_failed_publication_cleans_only_new_branch(tmp_path: Path) -> None:
    result, calls = _run(tmp_path, True, "review-publisher", "true", git_ok=True)
    assert result.returncode != 0
    assert "gh pr create --draft" in calls
    assert "git push origin HEAD:refs/heads/fixture-refresh/987654-2" in calls
    assert "git push origin :refs/heads/fixture-refresh/987654-2" in calls
    assert "git push --force" not in calls


def test_cleanup_trap_is_cancelled_only_after_pr_creation() -> None:
    code = _script()
    assert 'unpublished_branch="$branch"' in code
    assert 'unpublished_branch=""' in code
    assert code.index('gh pr create --draft') < code.rindex('unpublished_branch=""')
    assert 'git push origin ":refs/heads/$unpublished_branch"' in code


def test_successful_publication_preserves_authorized_action_order(tmp_path: Path) -> None:
    result, calls = _run(tmp_path, True, "review-publisher", "true", git_ok=True, pr_ok=True)
    assert result.returncode == 0
    actions = calls.splitlines()
    checkout = next(i for i, line in enumerate(actions) if line.startswith("git checkout -b "))
    publish = next(i for i, line in enumerate(actions) if line.startswith("git push origin HEAD:refs/heads/"))
    create_pr = next(i for i, line in enumerate(actions) if line.startswith("gh pr create --draft "))
    assert actions.index("gh api user --jq .login") < checkout < publish < create_pr
    assert "git push origin :refs/heads/" not in calls
    assert "git push --force" not in calls

