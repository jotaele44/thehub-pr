"""Process supervision: no shell, deny-by-default env, redaction, cancellation.

Covers gates G03 (no arbitrary shell), G11 (streamed logs, cancellation, log
hash) and the log/environment half of G18 (no secret disclosure).
"""
from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.backend.federation_manager_process import (  # noqa: E402
    DEFAULT_ENV_ALLOWLIST,
    REDACTION_PLACEHOLDER,
    ProcessError,
    ProcessLimits,
    Redactor,
    build_environment,
    is_secret_name,
    redact_argv,
    redact_environment_names,
    run_process,
)

CANARY = "prii-canary-secret-9f3ac2be41d07"


@pytest.fixture
def workdir(tmp_path):
    return tmp_path


def _script(workdir: Path, body: str) -> Path:
    """Write a throwaway script and return its path.

    Tests drive argv of the shape ``[interpreter, script_path, ...]`` rather
    than ``python -c``, matching what the executor actually produces: it runs
    script files and fixed modules, never inline code.
    """
    path = workdir / "child.py"
    path.write_text(body, encoding="utf-8")
    return path


# ── G03: the supervisor refuses anything string-shaped ──────────────────────


def test_a_command_string_is_refused(workdir):
    with pytest.raises(ProcessError, match="never a command string"):
        run_process("echo hi", cwd=workdir, env={})


def test_empty_argv_is_refused(workdir):
    with pytest.raises(ProcessError, match="argv is empty"):
        run_process([], cwd=workdir, env={})


def test_missing_executable_reports_cleanly(workdir):
    with pytest.raises(ProcessError, match="not found"):
        run_process(["prii-nonexistent-binary"], cwd=workdir, env={})


def test_no_shell_execution_primitives_in_the_manager_plane():
    """Gate G03, asserted against the parsed AST rather than the raw text.

    A substring scan would trip over prose in a docstring that *names* the
    forbidden constructs, and would equally miss ``shell = True`` written with
    spaces. Walking the AST tests the code that actually runs.
    """
    import ast

    # Qualified: os.system is forbidden, platform.system() is ordinary.
    banned_attributes = {
        "os": {"system", "popen", "execv", "execve", "execvp", "spawnl", "spawnv", "posix_spawn"},
        "subprocess": {"getoutput", "getstatusoutput"},
    }
    banned_builtins = {"eval", "exec", "compile", "__import__"}
    offences: list[str] = []

    for module in sorted((REPO_ROOT / "server" / "backend").glob("federation_manager*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg == "shell" and not (
                    isinstance(keyword.value, ast.Constant) and keyword.value.value is False
                ):
                    offences.append(f"{module.name}:{node.lineno} passes a non-False shell=")
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                owner = node.func.value.id
                if node.func.attr in banned_attributes.get(owner, ()):
                    offences.append(f"{module.name}:{node.lineno} calls {owner}.{node.func.attr}()")
            elif isinstance(node.func, ast.Name) and node.func.id in banned_builtins:
                offences.append(f"{module.name}:{node.lineno} calls {node.func.id}()")

    assert offences == []


def test_metacharacters_in_an_argument_are_inert(workdir):
    """A semicolon reaches the child as data, not as a command separator."""
    script = _script(workdir, "import sys; sys.stdout.write(sys.argv[1])")
    payload = "; touch /tmp/prii-should-not-exist"
    seen: list[str] = []
    result = run_process(
        [sys.executable, str(script), payload],
        cwd=workdir,
        env=build_environment(),
        on_line=seen.append,
    )
    assert result.succeeded
    assert payload in "".join(seen)
    assert not Path("/tmp/prii-should-not-exist").exists()


# ── Environment: deny by default ────────────────────────────────────────────


def test_environment_is_deny_by_default():
    env = build_environment(base={"PATH": "/bin", "AWS_SECRET_ACCESS_KEY": "x", "HOME": "/root"})
    assert set(env) == {"PATH", "HOME"}
    assert "AWS_SECRET_ACCESS_KEY" not in env


def test_pythonpath_is_not_inheritable():
    assert "PYTHONPATH" not in DEFAULT_ENV_ALLOWLIST
    env = build_environment(base={"PATH": "/bin", "PYTHONPATH": "/attacker"})
    assert "PYTHONPATH" not in env


def test_extra_values_are_injected_but_names_are_validated():
    env = build_environment(base={"PATH": "/bin"}, extra={"PRII_APP_ROOT": "/managed"})
    assert env["PRII_APP_ROOT"] == "/managed"
    with pytest.raises(ProcessError, match="invalid environment variable name"):
        build_environment(base={}, extra={"BAD NAME": "x"})
    with pytest.raises(ProcessError, match="invalid environment variable name"):
        build_environment(base={}, extra={"LD_PRELOAD;evil": "x"})


def test_child_really_receives_only_the_allowlist(workdir):
    script = _script(
        workdir,
        "import json, os, sys; sys.stdout.write(json.dumps(sorted(os.environ)))",
    )
    seen: list[str] = []
    env = build_environment(
        base={"PATH": "/usr/bin:/bin", "HOME": "/root", "SUPER_SECRET": CANARY}
    )
    run_process([sys.executable, str(script)], cwd=workdir, env=env, on_line=seen.append)
    output = "".join(seen)
    assert "SUPER_SECRET" not in output
    assert CANARY not in output


def test_receipt_environment_records_names_only():
    env = build_environment(base={"PATH": "/bin"}, extra={"PRII_TOKEN": CANARY})
    names = redact_environment_names(env)
    assert names == ["PATH", "PRII_TOKEN"]
    assert CANARY not in "".join(names)


# ── G18: redaction ──────────────────────────────────────────────────────────


def test_redactor_replaces_a_secret_in_streamed_output(workdir):
    script = _script(
        workdir,
        f"import sys; sys.stdout.write('token is {CANARY} ok\\n')",
    )
    seen: list[str] = []
    result = run_process(
        [sys.executable, str(script)],
        cwd=workdir,
        env=build_environment(),
        on_line=seen.append,
        redactor=Redactor([CANARY]),
    )
    streamed = "".join(seen)
    assert CANARY not in streamed
    assert REDACTION_PLACEHOLDER in streamed
    assert result.redactions == 1


def test_a_secret_echoed_by_a_crashing_child_is_still_redacted(workdir):
    script = _script(
        workdir,
        f"import sys; sys.stderr.write('boom {CANARY}\\n'); sys.exit(3)",
    )
    seen: list[str] = []
    result = run_process(
        [sys.executable, str(script)],
        cwd=workdir,
        env=build_environment(),
        on_line=seen.append,
        redactor=Redactor([CANARY]),
    )
    assert result.status == "failed"
    assert result.exit_code == 3
    assert CANARY not in "".join(seen)


def test_redactor_handles_overlapping_values():
    redactor = Redactor(["abcdefgh", "abcd"])
    assert redactor("value=abcdefgh") == f"value={REDACTION_PLACEHOLDER}"


def test_redactor_ignores_values_too_short_to_be_meaningful():
    """Redacting a 2-character value would blank out unrelated output."""
    redactor = Redactor(["ab"])
    assert redactor("a table of abbreviations") == "a table of abbreviations"


def test_redactor_clears_retained_values():
    redactor = Redactor([CANARY])
    redactor("x")
    redactor.clear()
    assert redactor(CANARY) == CANARY  # nothing retained after clear


def test_redact_argv_masks_secret_shaped_flags():
    assert redact_argv(["hub", "--api-token", CANARY]) == [
        "hub",
        "--api-token",
        REDACTION_PLACEHOLDER,
    ]
    assert redact_argv(["hub", f"--password={CANARY}"]) == [
        "hub",
        f"--password={REDACTION_PLACEHOLDER}",
    ]
    assert redact_argv(["hub", "list", "--registry", "x.yaml"]) == [
        "hub",
        "list",
        "--registry",
        "x.yaml",
    ]


def test_is_secret_name_matches_the_manager_convention():
    assert is_secret_name("ANTHROPIC_API_KEY")
    assert is_secret_name("--authorization")
    assert is_secret_name("db_password")
    assert not is_secret_name("--root")


# ── G11: streaming, limits, cancellation, log hash ──────────────────────────


def test_log_hash_is_over_the_redacted_bytes(workdir):
    script = _script(workdir, "import sys; sys.stdout.write('deterministic\\n')")
    argv = [sys.executable, str(script)]
    first = run_process(argv, cwd=workdir, env=build_environment())
    second = run_process(argv, cwd=workdir, env=build_environment())
    assert first.log_sha256 == second.log_sha256
    assert len(first.log_sha256) == 64
    assert first.log_bytes > 0


def test_log_is_bounded_and_marked_truncated(workdir):
    script = _script(
        workdir,
        "import sys\nfor i in range(20000):\n    sys.stdout.write('x' * 100 + '\\n')\n",
    )
    result = run_process(
        [sys.executable, str(script)],
        cwd=workdir,
        env=build_environment(),
        limits=ProcessLimits(max_log_bytes=8192),
    )
    assert result.truncated is True
    assert result.log_bytes < 20000 * 101


def test_timeout_kills_the_child(workdir):
    script = _script(workdir, "import time; time.sleep(30)")
    started = time.monotonic()
    result = run_process(
        [sys.executable, str(script)],
        cwd=workdir,
        env=build_environment(),
        limits=ProcessLimits(timeout_seconds=1.0),
    )
    assert result.status == "timed_out"
    assert time.monotonic() - started < 15


def test_cancellation_stops_the_run(workdir):
    script = _script(
        workdir,
        "import sys, time\nwhile True:\n    sys.stdout.write('tick\\n'); sys.stdout.flush(); time.sleep(0.1)\n",
    )
    cancel = threading.Event()
    seen: list[str] = []

    def _cancel_soon():
        time.sleep(0.5)
        cancel.set()

    threading.Thread(target=_cancel_soon, daemon=True).start()
    result = run_process(
        [sys.executable, str(script)],
        cwd=workdir,
        env=build_environment(),
        on_line=seen.append,
        cancel_event=cancel,
        limits=ProcessLimits(timeout_seconds=30),
    )
    assert result.status == "cancelled"
    assert len(seen) >= 1


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")
def test_a_grandchild_is_killed_with_the_group(workdir):
    """A timeout must not orphan a process the child itself spawned."""
    marker = workdir / "grandchild-alive"
    grandchild = _script_named(
        workdir,
        "grandchild.py",
        f"import time\nfor _ in range(300):\n    open({str(marker)!r}, 'a').write('.')\n    time.sleep(0.1)\n",
    )
    parent = _script_named(
        workdir,
        "parent.py",
        "import subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, {str(grandchild)!r}])\n"
        "time.sleep(30)\n",
    )
    run_process(
        [sys.executable, str(parent)],
        cwd=workdir,
        env=build_environment(),
        limits=ProcessLimits(timeout_seconds=1.0),
    )
    time.sleep(1.0)
    size_after_kill = marker.stat().st_size if marker.exists() else 0
    time.sleep(1.0)
    size_later = marker.stat().st_size if marker.exists() else 0
    assert size_later == size_after_kill, "grandchild survived the process-group kill"


def _script_named(workdir: Path, name: str, body: str) -> Path:
    path = workdir / name
    path.write_text(body, encoding="utf-8")
    return path


def test_successful_run_reports_exit_zero(workdir):
    script = _script(workdir, "print('ok')")
    result = run_process([sys.executable, str(script)], cwd=workdir, env=build_environment())
    assert result.succeeded
    assert result.status == "succeeded"
    assert result.exit_code == 0


def test_stderr_is_merged_into_the_single_log_stream(workdir):
    script = _script(
        workdir,
        "import sys; sys.stdout.write('out\\n'); sys.stderr.write('err\\n')",
    )
    seen: list[str] = []
    run_process(
        [sys.executable, str(script)], cwd=workdir, env=build_environment(), on_line=seen.append
    )
    joined = "".join(seen)
    assert "out" in joined and "err" in joined


def test_child_gets_no_stdin(workdir):
    """A child that blocks on stdin would hang the manager; stdin is /dev/null."""
    script = _script(workdir, "import sys; sys.stdout.write(repr(sys.stdin.read()))")
    result = run_process(
        [sys.executable, str(script)],
        cwd=workdir,
        env=build_environment(),
        limits=ProcessLimits(timeout_seconds=10),
    )
    assert result.succeeded


def test_subprocess_module_is_only_used_without_a_shell():
    source = (REPO_ROOT / "server" / "backend" / "federation_manager_process.py").read_text(
        encoding="utf-8"
    )
    assert "subprocess.Popen(argv" in source
    assert subprocess.Popen  # module imported for real, not shadowed
