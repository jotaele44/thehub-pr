"""Run tools/federation_template_sync_pr.sh against a real local git origin.

Each case builds a producer checkout whose ``origin`` is a local bare
repository, applies the edits a re-render would make, and runs the script with
a stub ``gh`` on PATH that logs every call. That covers the token preflight,
the pin-only skip and the standing branch whose PR is updated rather than
duplicated.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "federation_template_sync_pr.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "federation-template-sync.yml"

OLD_PIN = "1" * 40
HUB_SHA = "abcdef0123456789abcdef0123456789abcdef01"
BRANCH = "federation-template-sync"
PIN_FILE = ".github/workflows/template-drift.yml"
PERMISSIONS = "Contents, Pull requests and Workflows: Read and write"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="needs bash and git",
)

DRIFT_YML = """\
name: Template drift
on: [pull_request]
jobs:
  drift:
    runs-on: ubuntu-latest
    env:
      PRII_TEMPLATE_REF: {pin}
    steps:
      - run: echo checking
"""

# Logs argv on one line (request bodies contain newlines), then answers the three calls the script makes. OPEN_PR is the
# number an open sync PR would have ("" for none); GH_FAIL=1 makes every call fail.
GH_STUB = """#!/bin/sh
printf '%s' "$*" | tr '\\n' ' ' >> "$GH_LOG"
echo >> "$GH_LOG"
if [ "$GH_FAIL" = 1 ]; then exit 1; fi
case "$*" in
  *"-X PATCH"*) echo "https://github.com/example/pr/$OPEN_PR" ;;
  *"-X POST"*) echo "https://github.com/example/pr/new" ;;
  *) [ -n "$OPEN_PR" ] && echo "$OPEN_PR" ;;
esac
exit 0
"""


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd, env=_git_env(), text=True, capture_output=True, check=True,
    ).stdout


def _git_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("GH_TOKEN", None)
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})
    return env


@pytest.fixture
def producer(tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)],
                   env=_git_env(), check=True)
    repo = tmp_path / "producer"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / ".github/workflows").mkdir(parents=True)
    (repo / PIN_FILE).write_text(DRIFT_YML.format(pin=OLD_PIN))
    (repo / ".github/workflows/codeql.yml").write_text("name: CodeQL\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "push", "-q", "origin", "main")
    return repo


def _repin(repo: Path) -> None:
    (repo / PIN_FILE).write_text(DRIFT_YML.format(pin=HUB_SHA))


def _template_change(repo: Path) -> None:
    _repin(repo)
    (repo / ".github/workflows/codeql.yml").write_text("name: CodeQL\n# bumped\n")


def _run(repo: Path, *, token: str = "", open_pr: str = "", gh_fail: bool = False):
    bin_dir = repo.parent / "bin"
    bin_dir.mkdir(exist_ok=True)
    gh = bin_dir / "gh"
    gh.write_text(GH_STUB)
    gh.chmod(0o755)
    log = repo.parent / "gh.log"
    env = _git_env()
    env.update({
        "PATH": f"{bin_dir}{os.pathsep}{env.get('PATH', '')}",
        "REPO": "example-pr",
        "OWNER": "example",
        "HUB_SHA": HUB_SHA,
        "GH_TOKEN": token,
        "GH_LOG": str(log),
        "OPEN_PR": open_pr,
        "GH_FAIL": "1" if gh_fail else "0",
        # Never the runner's own job summary when the suite runs in Actions.
        "GITHUB_STEP_SUMMARY": str(repo.parent / "summary.md"),
    })
    result = subprocess.run(["bash", str(SCRIPT)], cwd=repo, env=env,
                            text=True, capture_output=True, check=False)
    calls = log.read_text().splitlines() if log.exists() else []
    return result, calls


def _remote_branch(repo: Path) -> str:
    return _git(repo, "ls-remote", "origin", f"refs/heads/{BRANCH}").strip()


def _refuse_pushes(repo: Path) -> None:
    _git(repo, "remote", "set-url", "--push", "origin", str(repo.parent / "missing.git"))


def _reject_real_pushes(repo: Path) -> None:
    # Hooks do not run on a dry run, so the preflight passes and the push fails,
    # as GitHub does when a token without Workflows write touches a workflow file.
    hook = repo.parent / "origin.git" / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho 'refusing to update workflow .github/workflows/template-drift.yml' >&2\nexit 1\n")
    hook.chmod(0o755)


def test_no_drift_without_token_does_nothing(producer: Path) -> None:
    result, calls = _run(producer)
    assert result.returncode == 0, result.stderr
    assert "already matches the canonical templates" in result.stdout
    assert calls == []
    assert _remote_branch(producer) == ""


def test_no_drift_with_token_still_runs_the_preflight(producer: Path) -> None:
    _refuse_pushes(producer)
    result, calls = _run(producer, token="t")
    assert result.returncode == 1
    assert "dry-run push to example/example-pr was refused" in result.stdout
    assert PERMISSIONS in result.stdout
    assert calls == []


def test_no_drift_with_a_writable_token_pushes_nothing(producer: Path) -> None:
    result, calls = _run(producer, token="t")
    assert result.returncode == 0, result.stderr
    assert "already matches" in result.stdout
    assert _remote_branch(producer) == ""
    assert not any("-X " in call for call in calls)
    assert "Stale sync PR" not in result.stdout


def test_no_drift_warns_about_an_open_sync_pr(producer: Path) -> None:
    result, _ = _run(producer, token="t", open_pr="9")
    assert result.returncode == 0, result.stderr
    assert "example/example-pr#9 is open" in result.stdout


def test_pin_only_change_opens_no_pr(producer: Path) -> None:
    _repin(producer)
    result, calls = _run(producer, token="t")
    assert result.returncode == 0, result.stderr
    assert "only PRII_TEMPLATE_REF would change" in result.stdout
    assert _remote_branch(producer) == ""
    assert not any("-X " in call for call in calls)
    assert _git(producer, "rev-parse", "--abbrev-ref", "HEAD").strip() == "main"


def test_pin_only_change_warns_about_an_open_sync_pr(producer: Path) -> None:
    _repin(producer)
    result, _ = _run(producer, token="t", open_pr="4")
    assert result.returncode == 0, result.stderr
    assert "example/example-pr#4 is open" in result.stdout


def test_other_edit_to_the_drift_gate_is_real_drift(producer: Path) -> None:
    (producer / PIN_FILE).write_text(DRIFT_YML.format(pin=HUB_SHA) + "# changed\n")
    result, calls = _run(producer, token="t")
    assert result.returncode == 0, result.stderr
    assert "only PRII_TEMPLATE_REF" not in result.stdout
    assert any("-X POST" in call for call in calls)


def test_new_rendered_file_is_real_drift(producer: Path) -> None:
    _repin(producer)
    (producer / ".github/workflows/pip-audit.yml").write_text("name: pip-audit\n")
    result, calls = _run(producer, token="t")
    assert result.returncode == 0, result.stderr
    assert any("-X POST" in call for call in calls)
    files = _git(producer, "show", "--name-only", "--format=", BRANCH).split()
    assert ".github/workflows/pip-audit.yml" in files


def test_drift_without_token_is_a_dry_run(producer: Path) -> None:
    _template_change(producer)
    result, calls = _run(producer)
    assert result.returncode == 0, result.stderr
    assert "dry run; no PR opened" in result.stdout
    assert calls == []
    assert _remote_branch(producer) == ""


def test_dry_run_with_drift_warns_and_writes_the_job_summary(producer: Path) -> None:
    _template_change(producer)
    result, calls = _run(producer)
    summary = producer.parent / "summary.md"
    assert result.returncode == 0, result.stderr
    assert "::warning::example-pr drifted" in result.stdout
    text = summary.read_text()
    assert "example-pr: drift not propagated (dry run)" in text
    assert f"--template-ref {HUB_SHA}" in text
    assert "codeql.yml" in text
    assert calls == []


def test_drift_opens_one_pr_on_the_standing_branch(producer: Path) -> None:
    _template_change(producer)
    result, calls = _run(producer, token="t")
    assert result.returncode == 0, result.stderr
    head = _git(producer, "rev-parse", "HEAD").strip()
    assert _remote_branch(producer).split()[0] == head
    assert _git(producer, "show", "HEAD:" + PIN_FILE).count(HUB_SHA) == 1
    subject = _git(producer, "log", "-1", "--format=%s")
    assert HUB_SHA[:12] in subject
    assert calls[0] == f"api repos/example/example-pr/pulls?head=example:{BRANCH}&state=open --jq .[0].number // empty"
    (create,) = [c for c in calls if "-X POST" in c]
    assert f"head={BRANCH}" in create and "base=main" in create
    assert f"title=Sync shared federation boilerplate from thehub-pr@{HUB_SHA[:12]}" in create
    assert "Do not push to it by hand" in create
    assert not any("-X PATCH" in c for c in calls)
    assert "Opened https://github.com/example/pr/new" in result.stdout


def test_open_pr_is_force_updated_not_duplicated(producer: Path) -> None:
    # An earlier run's branch, not an ancestor of the new commit: only a force push replaces it.
    _git(producer, "checkout", "-q", "-b", BRANCH)
    (producer / "stale.txt").write_text("old sync\n")
    _git(producer, "add", "-A")
    _git(producer, "commit", "-q", "-m", "old sync")
    _git(producer, "push", "-q", "origin", BRANCH)
    _git(producer, "checkout", "-q", "main")
    _template_change(producer)
    result, calls = _run(producer, token="t", open_pr="17")
    assert result.returncode == 0, result.stderr
    head = _git(producer, "rev-parse", "HEAD").strip()
    assert _remote_branch(producer).split()[0] == head
    assert "stale.txt" not in _git(producer, "ls-tree", "-r", "--name-only", head)
    (edit,) = [c for c in calls if "-X PATCH" in c]
    assert edit.startswith("api -X PATCH repos/example/example-pr/pulls/17 ")
    assert not any("-X POST" in c for c in calls)
    assert "Updated https://github.com/example/pr/17" in result.stdout


def test_refused_real_push_names_the_workflows_permission(producer: Path) -> None:
    _template_change(producer)
    _reject_real_pushes(producer)
    result, calls = _run(producer, token="t")
    assert result.returncode == 1
    assert "refused after the dry run passed" in result.stdout
    assert "Workflows: Read and write is missing" in result.stdout
    assert calls == []


def test_pull_request_api_failure_fails_the_job(producer: Path) -> None:
    _template_change(producer)
    result, _ = _run(producer, token="t", gh_fail=True)
    assert result.returncode == 1
    assert "could not list example/example-pr pull requests" in result.stdout
    assert PERMISSIONS in result.stdout


def test_workflow_runs_the_script_from_the_producer_checkout() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    steps = yaml.safe_load(text)["jobs"]["propagate"]["steps"]
    (step,) = [s for s in steps if "federation_template_sync_pr.sh" in s.get("run", "")]
    assert step["run"] == 'bash "$GITHUB_WORKSPACE/thehub-pr/tools/federation_template_sync_pr.sh"'
    assert step["working-directory"] == "${{ matrix.repo }}"
    assert step["env"] == {
        "REPO": "${{ matrix.repo }}",
        "HUB_SHA": "${{ github.sha }}",
        "GH_TOKEN": "${{ secrets.SYNC_PAT }}",
    }
    assert steps[-1] is step
    render = [s for s in steps if "render_federation_templates.py" in s.get("run", "")]
    assert len(render) == 1 and "--template-ref ${{ github.sha }}" in render[0]["run"]
    assert "gh pr create" not in text
    assert "github.run_id" not in text
