"""Producer independence must survive malformed input and partial failures."""
import json
import subprocess

import pytest

from hub.cli import main
from hub.fetch import _subprocess_runner, clone_or_pull, export_command, fetch_all
from hub.registry import Producer, Registry


def registry(*paths):
    return Registry(hub="thehub-pr", schema_version="hub_registry_v1", producers=[
        Producer(program_id=f"p{i}", repo=f"owner/p{i}", role="test", local_path=str(path))
        for i, path in enumerate(paths)
    ])


@pytest.mark.parametrize("payload", [[], None, 3, {"hub_callable_commands": []},
    {"hub_callable_commands": {"export_canonical": ["python3", "export.py"]}},
    {"hub_callable_commands": {"export_canonical": "python3 'unterminated"}},
])
def test_malformed_export_declaration_is_refused(tmp_path, payload):
    (tmp_path / "federation.json").write_text(json.dumps(payload))
    assert export_command(tmp_path) is None


@pytest.mark.parametrize("failure", [
    subprocess.CalledProcessError(1, ["private-command"], stderr="private-output"),
    subprocess.TimeoutExpired(["private-command"], 300),
    OSError("private-path"),
])
def test_export_failure_does_not_omit_later_producers(tmp_path, failure):
    paths = [tmp_path / f"p{i}" for i in range(6)]
    for path in paths:
        path.mkdir()
        (path / "federation.json").write_text(json.dumps({
            "hub_callable_commands": {"export_canonical": "python3 export.py"},
        }))
    calls = []

    def run(cmd, cwd):
        calls.append(cwd)
        if cwd == str(paths[1]):
            raise failure

    results = fetch_all(registry(*paths), tmp_path, run_export=True, runner=run)
    assert len(results) == len(calls) == 6
    assert [row["status"] for row in results] == ["PASS", "FAIL", "PASS", "PASS", "PASS", "PASS"]
    assert results[1]["exported"] is False
    assert results[1]["failed_stage"] == "export"
    assert all(marker not in json.dumps(results) for marker in
               ("private-command", "private-output", "private-path"))


def test_missing_export_command_fails_requested_export(tmp_path):
    result = fetch_all(registry(tmp_path), tmp_path, run_export=True)[0]
    assert result["status"] == "FAIL"
    assert result["error_code"] == "export_command_unavailable"


def test_missing_local_checkout_is_not_success(tmp_path):
    path = tmp_path / "absent"
    result = fetch_all(registry(path), tmp_path)[0]
    assert result["status"] == "FAIL"
    assert not path.exists()


def test_worktree_git_file_is_recognized(tmp_path):
    (tmp_path / ".git").write_text("gitdir: /irrelevant/fake-admin")
    calls = []
    clone_or_pull("owner/repo", tmp_path, runner=lambda cmd, cwd: calls.append(cmd))
    assert len(calls) == 1 and "pull" in calls[0]


def test_process_runtime_is_bounded(monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: calls.append(kwargs))
    _subprocess_runner(["python3", "export.py"])
    assert 0 < calls[0]["timeout"] <= 300


def test_cli_reports_failure_and_keeps_full_denominator(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("hub.cli.load_registry", lambda _: registry(tmp_path))
    monkeypatch.setattr("hub.cli.fetch_all", lambda *a, **k: [
        dict(program_id="p0", action="local", exported=False, base=str(tmp_path),
             status="FAIL", failed_stage="export", error_code="export_command_unavailable"),
    ])
    assert main(["fetch", "--root", str(tmp_path), "--run"]) == 1
    output = capsys.readouterr().out
    assert "export_command_unavailable" in output
    assert "1 failed" in output


def test_fetch_failure_is_accounted_without_export(tmp_path):
    reg = Registry(hub="thehub-pr", schema_version="hub_registry_v1", producers=[
        Producer(program_id="remote", repo="owner/remote", role="test"),
        Producer(program_id="local", repo="owner/local", role="test", local_path=str(tmp_path)),
    ])
    def run(cmd, cwd):
        raise subprocess.CalledProcessError(128, cmd)
    results = fetch_all(reg, tmp_path / "workspace", runner=run)
    assert len(results) == 2
    assert results[0]["failed_stage"] == "fetch"
    assert results[1]["status"] == "PASS"
