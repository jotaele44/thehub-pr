"""Clone/refresh producer checkouts into a workspace so the Hub can aggregate
straight from GitHub instead of assuming pre-existing local checkouts.

``hub aggregate`` resolves each producer's package at
``<root>/<repo_name>/<export_path>``. This module populates that ``<root>``:

  * ``clone_or_pull`` — shallow-clone a producer repo (or fast-forward pull it
    if already present).
  * ``export_command`` — read a producer's ``federation.json``
    ``hub_callable_commands.export_canonical`` so the Hub can materialise the
    canonical streams.
  * ``fetch_all`` — orchestrate the above across every registered producer.

All process execution goes through an injectable ``runner`` so the orchestration
logic is unit-testable offline (no network, no real git). The default runner
shells out via ``subprocess``.
"""
from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

GIT_URL = "https://github.com/{repo}.git"

# Executables the Hub will accept as the first token of a hub_callable_commands
# value. Operators may extend this list; it must never include shell built-ins
# or interpreters that trivially escape sandboxing (e.g. perl, ruby, node).
_ALLOWED_EXECUTABLES = frozenset({
    "bash", "make", "mypy", "pytest", "python", "python3", "ruff", "sh", "uv",
})

# Characters that would allow shell injection if passed to a subprocess runner
# that re-invokes a shell (sh -c, os.system, etc.).
_SHELL_METACHAR = frozenset(";|&`$><\\\n\r")

# Shell interpreters that accept -c <string> for arbitrary code execution.
_SHELL_EVAL_INTERPRETERS = frozenset({"bash", "sh"})

# Python interpreters that can run inline code (-c/-e), an arbitrary module
# (-m, e.g. `python -m pip install ...` / `python -m timeit -s ...`), or a
# program read from stdin (-) — all of which sidestep "run a script file".
_PY_INTERPRETERS = frozenset({"python", "python3"})
_PY_CODE_EXEC_LONG = ("--command", "--eval")
_PY_CODE_EXEC_SHORT = frozenset("cem")
# Python options that consume a value (the rest of their token, or the next
# token). They must be skipped so an option value like the `ignore` in
# `-W ignore` is not mistaken for the script path, which would hide a later -c/-m.
_PY_VALUE_SHORT = frozenset("WX")
_PY_VALUE_LONG = ("--check-hash-based-pycs",)

# A runner takes a command (token list) and an optional cwd, and runs it.
Runner = Callable[[Sequence[str], Optional[str]], Any]


def _subprocess_runner(cmd: Sequence[str], cwd: Optional[str] = None):
    """Default runner: run `cmd`, raising CalledProcessError on non-zero exit."""
    return subprocess.run(
        list(cmd), cwd=cwd, check=True, capture_output=True, text=True, timeout=300,
    )


def clone_or_pull(
    repo: str,
    dest,
    runner: Runner = _subprocess_runner,
    depth: int = 1,
) -> str:
    """Shallow-clone ``repo`` into ``dest``, or fast-forward pull if it already
    has a ``.git``. Returns ``"cloned"`` or ``"pulled"``."""
    dest = Path(dest)
    if (dest / ".git").is_dir() or (dest / ".git").is_file():
        runner(["git", "-C", str(dest), "pull", "--ff-only", "--quiet"], None)
        return "pulled"
    dest.parent.mkdir(parents=True, exist_ok=True)
    runner(["git", "clone", "--depth", str(depth), "--quiet", GIT_URL.format(repo=repo), str(dest)], None)
    return "cloned"


def _py_executes_code(args: List[str]) -> bool:
    """True if a python interpreter's options run code instead of a script file.

    Models python's left-to-right option parsing so that options which *consume
    a value* (``-W arg`` / ``-X opt`` / ``--check-hash-based-pycs arg``) do not
    hide a later ``-c``/``-m`` by being mistaken for the script path. Scanning
    stops at the real script path (the first non-option token that is not an
    option's value), after which tokens are the script's own argv — so
    ``export.py -c config.yaml`` is not mistaken for ``python -c``.

    Catches bare ``-`` (stdin), ``--command``/``--eval``, and ``-c``/``-e``/``-m``
    in bare, attached (``-mpip``), and combined (``-Ic``) short-option forms.
    """
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue  # this token is the previous option's value
        if not arg.startswith("-"):
            return False  # the script path; remaining tokens are its arguments
        if arg == "-":
            return True  # read program from stdin
        if arg.startswith(_PY_CODE_EXEC_LONG):
            return True
        if arg.startswith("--"):
            # A long option. `--check-hash-based-pycs arg` consumes the next token
            # unless the value is attached with `=`.
            if arg in _PY_VALUE_LONG:
                skip_next = True
            continue
        # A short-option cluster, e.g. -O, -Ic, -W, -Wignore, -OWignore.
        for i in range(1, len(arg)):
            ch = arg[i]
            if ch in _PY_CODE_EXEC_SHORT:  # -c/-e/-m: inline code / module
                return True
            if ch in _PY_VALUE_SHORT:  # -W/-X consume the rest, or the next token
                if i == len(arg) - 1:
                    skip_next = True
                break
    return False


def _validate_command(cmd: str) -> Optional[List[str]]:
    """Split and allowlist-check a producer command string.

    Returns the token list when the command is safe, None otherwise. Safety
    requires: no shell metacharacters; the first token is a bare allowlisted
    executable name (no path separator — so ``/tmp/python`` cannot smuggle a
    different binary past a basename check); shells are not invoked with ``-c``;
    and python interpreters run a script file rather than inline code (``-c``/
    ``-e``), an arbitrary module (``-m``), or a program from stdin (``-``).
    """
    if not isinstance(cmd, str) or any(c in _SHELL_METACHAR for c in cmd):
        return None
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        return None
    if not tokens:
        return None
    executable = tokens[0]
    if "/" in executable or executable not in _ALLOWED_EXECUTABLES:
        return None
    if executable in _SHELL_EVAL_INTERPRETERS and "-c" in tokens[1:]:
        return None
    if executable in _PY_INTERPRETERS and _py_executes_code(tokens[1:]):
        return None
    return tokens


def export_command(base) -> Optional[List[str]]:
    """Return the producer's ``export_canonical`` command as token list, read from
    ``<base>/federation.json``. ``None`` when the file, command, or allowlist check is absent."""
    fed = Path(base) / "federation.json"
    if not fed.is_file():
        return None
    try:
        data = json.loads(fed.read_text())
    except (ValueError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    commands = data.get("hub_callable_commands")
    if not isinstance(commands, dict):
        return None
    cmd = commands.get("export_canonical")
    return _validate_command(cmd) if cmd else None


def fetch_all(
    registry,
    workspace,
    run_export: bool = False,
    runner: Runner = _subprocess_runner,
    depth: int = 1,
) -> List[Dict[str, Any]]:
    """For each registered producer: clone/pull into ``<workspace>/<repo_name>``
    (unless it has a ``local_path``), then optionally run its ``export_canonical``
    command to materialise the package. Returns a per-producer result list.

    Operational failures remain attached to their producer so independent work
    continues. Callers must inspect ``status``; a requested but unavailable
    export is a failure. Raw process output is excluded from these results
    because producer commands may print credentials or private source content.
    No automatic retries or new source downloads follow an export failure.
    """
    ws = Path(workspace)
    results: List[Dict[str, Any]] = []
    for p in registry.producers:
        base = Path(p.local_path) if p.local_path else ws / p.repo_name
        result: Dict[str, Any] = {
            "program_id": p.program_id, "repo": p.repo, "base": str(base),
            "action": "local" if p.local_path else "pending",
            "exported": False, "status": "PASS",
        }
        stage = "fetch"
        try:
            if p.local_path:
                if not base.is_dir():
                    raise FileNotFoundError("local checkout unavailable")
            else:
                result["action"] = clone_or_pull(p.repo, base, runner=runner, depth=depth)
            if run_export:
                stage = "export"
                cmd = export_command(base)
                if cmd is None:
                    result.update(status="FAIL", failed_stage=stage,
                                  error_code="export_command_unavailable")
                else:
                    runner(cmd, str(base))
                    result["exported"] = True
        except (OSError, subprocess.SubprocessError) as exc:
            result.update(status="FAIL", failed_stage=stage, error_code=type(exc).__name__)
        results.append(result)
    return results
