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

# Python interpreters the Hub will use to run a producer's in-tree export script.
# Matched as exact bare names. poetry / uv / make are intentionally NOT allowed:
# they are general-purpose runners ("poetry run <prog>", "uv pip install <pkg>",
# "make <target>") that would let a compromised federation.json launch arbitrary
# programs or fetch and execute remote packages.
_ALLOWED_INTERPRETERS = {"python", "python3"}

# Short option letters that make an interpreter run code/modules instead of an
# in-tree script file: -c/-e execute an inline string; -m runs an arbitrary
# module (e.g. `-m pip install ...`, `-m timeit -s ...`) which is itself a code-
# or package-execution vector.
_CODE_EXEC_SHORT_FLAGS = frozenset("cem")
_CODE_EXEC_LONG_FLAGS = ("--command", "--eval")


def _is_code_exec_flag(arg: str) -> bool:
    """True if *arg* makes the interpreter run code/modules instead of a file.

    Catches every spelling: a bare ``-`` (read program from stdin); long
    ``--command``/``--eval`` (with or without ``=value``); bare short ``-c``/
    ``-e``/``-m``; attached forms (``-cCODE``/``-mpip``); and combined clusters
    (``-Ic`` / ``-Im``) where other single-char options precede the exec flag.
    """
    if arg == "-":
        return True
    if arg.startswith(_CODE_EXEC_LONG_FLAGS):
        return True
    if len(arg) >= 2 and arg[0] == "-" and arg[1] != "-":
        for ch in arg[1:]:
            if ch in _CODE_EXEC_SHORT_FLAGS:
                return True
            if not ch.isalpha():  # reached an attached value (e.g. -W0) — stop
                break
    return False


def _in_tree_file(token: str, base: Path) -> bool:
    """True if *token* is a relative path to an existing file inside *base*."""
    p = Path(token)
    if p.is_absolute() or ".." in p.parts:
        return False
    resolved = (base / p).resolve()
    return resolved.is_relative_to(base.resolve()) and resolved.is_file()


def _escapes_base(token: str) -> bool:
    """True if *token* is an absolute path or climbs out of the tree via ``..``."""
    p = Path(token)
    return p.is_absolute() or ".." in p.parts


def _safe_cmd(cmd: List[str], base: Path) -> List[str]:
    """Validate that a producer's ``export_canonical`` *cmd* is safe to execute.

    Accepts exactly two shapes, both of which run only the producer's own
    checked-in code:

    1. A Python interpreter (``python``/``python3``) running an **in-tree script
       file** — e.g. ``python3 scripts/federation_export.py --mode test`` (the
       shape every real producer uses). The command must reference a file that
       exists inside *base*, must not use a code/module-exec flag
       (``-c``/``-e``/``-m``/``--command``/``--eval``/``-``), and no argument may
       be an absolute path or use ``..`` traversal.
    2. An in-tree script invoked directly by **path** — e.g. ``scripts/export.sh``.
       The head must contain a path separator so ``subprocess`` resolves it
       relative to *base* rather than doing a ``$PATH`` lookup (a bare ``perl``
       would otherwise launch the *system* ``/usr/bin/perl`` even with a like-named
       decoy file committed in the repo). Arguments may not escape *base*.

    Everything else — arbitrary system binaries, bare interpreter names other than
    python, general-purpose runners (poetry/uv/make), inline code, module
    execution, and absolute/traversal paths — is refused. Running an in-tree
    script inherently trusts that script and the dependencies it imports; the goal
    here is to stop a compromised ``federation.json`` from *choosing* what runs,
    not to sandbox the producer's own code.
    """
    if not cmd:
        raise ValueError("Empty export_canonical command")
    base = Path(base)
    head = cmd[0]

    # Shape 2: an in-tree script as the program. It must be given as a path (with a
    # separator) so subprocess execs it relative to cwd=base, never via $PATH.
    if head not in _ALLOWED_INTERPRETERS:
        if "/" not in head or not _in_tree_file(head, base):
            raise ValueError(
                f"export_canonical program {head!r} must be a Python interpreter "
                f"({' / '.join(sorted(_ALLOWED_INTERPRETERS))}) or an in-tree script "
                f"referenced by path (e.g. 'scripts/export.py'). Refusing to execute."
            )
        for arg in cmd[1:]:
            if _escapes_base(arg):
                raise ValueError(
                    f"export_canonical argument {arg!r} is an absolute path or escapes "
                    f"the producer directory. Refusing to execute."
                )
        return cmd

    # Shape 1: an allowed Python interpreter. It must run an in-tree script file and
    # use no code/module-exec flag or escaping path.
    runs_in_tree_script = False
    for arg in cmd[1:]:
        if _is_code_exec_flag(arg):
            raise ValueError(
                f"export_canonical uses interpreter code/module-exec flag {arg!r}; "
                f"refusing to run arbitrary code. Run an in-tree script instead."
            )
        if _escapes_base(arg):
            raise ValueError(
                f"export_canonical argument {arg!r} is an absolute path or escapes "
                f"the producer directory. Refusing to execute."
            )
        if _in_tree_file(arg, base):
            runs_in_tree_script = True
    if not runs_in_tree_script:
        raise ValueError(
            f"export_canonical command {cmd!r} does not run a script inside the "
            f"producer directory. Refusing to execute."
        )
    return cmd


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
