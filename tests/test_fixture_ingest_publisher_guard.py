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


def _run(tmp_path: Path, configured: bool, login: str = "", push: str = ""):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    trace = tmp_path / "calls.txt"
    git = bin_dir / "git"
    git.write_text('#!/bin/sh\nprintf "git %s\\n" "$*" >> "$TRACE"\nexit 81\n')
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
        'fi\nexit 73\n'
    )
    gh.chmod(0o755)
    env = dict(os.environ)
    env.update({
        "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
        "HAS_SYNC_PAT": "true" if configured else "false",
        "LOGIN": login,
        "PUSH": push,
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
    assert content.index("git checkout -b") < content.index("git push origin")
    assert "always()" in WORKFLOW.read_text(encoding="utf-8")
