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

# A runner takes a command (token list) and an optional cwd, and runs it.
Runner = Callable[[Sequence[str], Optional[str]], Any]


def _subprocess_runner(cmd: Sequence[str], cwd: Optional[str] = None):
    """Default runner: run `cmd`, raising CalledProcessError on non-zero exit."""
    return subprocess.run(list(cmd), cwd=cwd, check=True, capture_output=True, text=True)


def clone_or_pull(
    repo: str,
    dest,
    runner: Runner = _subprocess_runner,
    depth: int = 1,
) -> str:
    """Shallow-clone ``repo`` into ``dest``, or fast-forward pull if it already
    has a ``.git``. Returns ``"cloned"`` or ``"pulled"``."""
    dest = Path(dest)
    if (dest / ".git").is_dir():
        runner(["git", "-C", str(dest), "pull", "--ff-only", "--quiet"], None)
        return "pulled"
    dest.parent.mkdir(parents=True, exist_ok=True)
    runner(["git", "clone", "--depth", str(depth), "--quiet", GIT_URL.format(repo=repo), str(dest)], None)
    return "cloned"


def _validate_command(cmd: str) -> Optional[List[str]]:
    """Split and allowlist-check a producer command string.

    Returns the token list when the command is safe, None otherwise.
    Safety requires: no shell metacharacters, and the first token's basename
    must be in _ALLOWED_EXECUTABLES.
    """
    if any(c in _SHELL_METACHAR for c in cmd):
        return None
    tokens = shlex.split(cmd)
    if not tokens:
        return None
    executable = Path(tokens[0]).name
    if executable not in _ALLOWED_EXECUTABLES:
        return None
    if executable in _SHELL_EVAL_INTERPRETERS and "-c" in tokens[1:]:
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
    cmd = (data.get("hub_callable_commands") or {}).get("export_canonical")
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
    command to materialise the package. Returns a per-producer result list."""
    ws = Path(workspace)
    results: List[Dict[str, Any]] = []
    for p in registry.producers:
        if p.local_path:
            base = Path(p.local_path)
            action = "local"
        else:
            base = ws / p.repo_name
            action = clone_or_pull(p.repo, base, runner=runner, depth=depth)

        exported = False
        if run_export:
            cmd = export_command(base)
            if cmd:
                runner(cmd, str(base))
                exported = True

        results.append(
            {
                "program_id": p.program_id,
                "repo": p.repo,
                "base": str(base),
                "action": action,
                "exported": exported,
            }
        )
    return results
