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

# A runner takes a command (token list) and an optional cwd, and runs it.
Runner = Callable[[Sequence[str], Optional[str]], Any]

# Executables allowed in export_canonical commands from producer federation.json files.
_ALLOWED_EXECUTABLES = {"python", "python3", "poetry", "make", "uv"}


def _safe_cmd(cmd: List[str], base: Path) -> List[str]:
    """Validate that *cmd* is safe to execute.

    Accepts commands whose first token is an allowed interpreter name or a
    path that resolves inside *base* (i.e. the cloned producer directory).
    Raises ValueError for anything else so that a compromised federation.json
    cannot execute arbitrary system binaries.
    """
    if not cmd:
        raise ValueError("Empty command")
    exe = Path(cmd[0])
    if exe.name in _ALLOWED_EXECUTABLES:
        return cmd
    if not exe.is_absolute():
        resolved = (base / exe).resolve()
        if resolved.is_relative_to(base.resolve()) and resolved.is_file():
            return cmd
    raise ValueError(
        f"export_canonical command {cmd[0]!r} is not in the allowed list "
        f"({', '.join(sorted(_ALLOWED_EXECUTABLES))}) and does not resolve "
        f"inside the producer directory. Refusing to execute."
    )


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


def export_command(base) -> Optional[List[str]]:
    """Return the producer's ``export_canonical`` command as token list, read from
    ``<base>/federation.json``. ``None`` when the file or command is absent."""
    fed = Path(base) / "federation.json"
    if not fed.is_file():
        return None
    try:
        data = json.loads(fed.read_text())
    except (ValueError, OSError):
        return None
    cmd = (data.get("hub_callable_commands") or {}).get("export_canonical")
    return shlex.split(cmd) if cmd else None


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
                runner(_safe_cmd(cmd, base), str(base))
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
