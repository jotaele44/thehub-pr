"""Fail-closed PRII federation workspace bootstrap and execution controls.

The canonical workspace contains ``thehub-pr`` and every registered producer as
immediate siblings. Local setup always creates one private ``.venv`` per
repository; this module never installs into the system interpreter.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .fetch import GIT_URL, _validate_command
from .registry import Registry, load_registry

HUB_REPOSITORY = "jotaele44/thehub-pr"
HUB_NAME = "thehub-pr"
CANONICAL_PYTHON = "3.11"
SHARED_PACKAGE_PATHS = (
    "packages/prii_maintenance",
    "packages/prii_export_utils",
)
Runner = Callable[[Sequence[str], Optional[str]], Any]


class WorkspaceError(RuntimeError):
    """Raised when a workspace or requested execution is not safe."""


@dataclass(frozen=True)
class RepoSpec:
    program_id: str
    repository: str
    name: str
    is_hub: bool = False


@dataclass(frozen=True)
class ActionReceipt:
    program_id: str
    action: str
    repository_path: str
    status: str
    detail: str = ""


def _subprocess_runner(cmd: Sequence[str], cwd: Optional[str] = None):
    return subprocess.run(list(cmd), cwd=cwd, check=True, capture_output=True, text=True)


def repository_specs(registry: Registry) -> List[RepoSpec]:
    specs = [RepoSpec(HUB_NAME, HUB_REPOSITORY, HUB_NAME, True)]
    seen = {HUB_NAME}
    for producer in registry.producers:
        if producer.repo_name in seen:
            raise WorkspaceError(f"duplicate repository name in registry: {producer.repo_name}")
        seen.add(producer.repo_name)
        specs.append(RepoSpec(producer.program_id, producer.repo, producer.repo_name, False))
    return specs


def _assert_root_not_nested(root: Path) -> None:
    resolved = root.expanduser().resolve()
    for parent in (resolved, *resolved.parents):
        if (parent / ".git").exists():
            raise WorkspaceError(
                f"workspace root {resolved} is nested inside Git checkout {parent}; "
                "choose a neutral parent directory"
            )


def _assert_immediate_child(root: Path, child: Path) -> None:
    if child.parent.resolve() != root.resolve():
        raise WorkspaceError(f"repository path is not an immediate workspace child: {child}")
    if child.is_symlink():
        raise WorkspaceError(f"repository path must not be a symlink: {child}")


def clone_or_update(repo: str, destination: Path, *, runner: Runner, depth: int) -> str:
    if destination.exists() and not (destination / ".git").is_dir():
        raise WorkspaceError(f"destination exists but is not a Git checkout: {destination}")
    if (destination / ".git").is_dir():
        runner(["git", "-C", str(destination), "pull", "--ff-only", "--quiet"], None)
        return "updated"
    destination.parent.mkdir(parents=True, exist_ok=True)
    runner(
        [
            "git",
            "clone",
            "--depth",
            str(depth),
            "--quiet",
            GIT_URL.format(repo=repo),
            str(destination),
        ],
        None,
    )
    return "cloned"


def clone_workspace(
    registry: Registry,
    root: os.PathLike[str] | str,
    *,
    depth: int = 1,
    runner: Runner = _subprocess_runner,
) -> List[ActionReceipt]:
    workspace = Path(root).expanduser()
    _assert_root_not_nested(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    receipts: List[ActionReceipt] = []
    for spec in repository_specs(registry):
        destination = workspace / spec.name
        _assert_immediate_child(workspace, destination)
        action = clone_or_update(spec.repository, destination, runner=runner, depth=depth)
        receipts.append(ActionReceipt(spec.program_id, action, str(destination), "ok"))
    return receipts


def _read_python_policy(repo: Path) -> Tuple[bool, str]:
    marker = repo / ".python-version"
    exception = repo / "federation" / "python-policy-exception.json"
    if marker.is_file():
        selected = marker.read_text(encoding="utf-8").strip()
        if selected == CANONICAL_PYTHON:
            return True, selected
        if exception.is_file():
            try:
                payload = json.loads(exception.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                return False, f"invalid exception: {exc}"
            if payload.get("selected_python") == selected and payload.get("reason"):
                return True, f"exception:{selected}"
        return False, f"expected {CANONICAL_PYTHON}, found {selected or '<empty>'}"
    if exception.is_file():
        return False, "exception exists without .python-version"
    return False, "missing .python-version"


def validate_workspace(registry: Registry, root: os.PathLike[str] | str) -> Dict[str, Any]:
    workspace = Path(root).expanduser().resolve()
    errors: List[str] = []
    repositories: List[Dict[str, Any]] = []
    try:
        _assert_root_not_nested(workspace)
    except WorkspaceError as exc:
        errors.append(str(exc))

    hub = workspace / HUB_NAME
    for spec in repository_specs(registry):
        repo = workspace / spec.name
        repo_errors: List[str] = []
        try:
            _assert_immediate_child(workspace, repo)
        except WorkspaceError as exc:
            repo_errors.append(str(exc))
        if not (repo / ".git").is_dir():
            repo_errors.append("missing .git checkout")
        if not spec.is_hub and not (repo / "federation.json").is_file():
            repo_errors.append("missing federation.json")
        python_ok, python_detail = _read_python_policy(repo)
        if not python_ok:
            repo_errors.append(f"python policy: {python_detail}")
        repositories.append(
            {
                "program_id": spec.program_id,
                "path": str(repo),
                "python_policy": python_detail,
                "errors": repo_errors,
            }
        )
        errors.extend(f"{spec.program_id}: {item}" for item in repo_errors)

    for relative in SHARED_PACKAGE_PATHS:
        if not (hub / relative).is_dir():
            errors.append(f"thehub-pr: missing shared package {relative}")

    venv_paths = [workspace / spec.name / ".venv" for spec in repository_specs(registry)]
    existing_venvs = [path.resolve() for path in venv_paths if path.exists()]
    if len(existing_venvs) != len(set(existing_venvs)):
        errors.append("multiple repositories resolve to the same .venv")

    return {
        "schema_version": "prii_workspace_validation_v1",
        "root": str(workspace),
        "canonical_python": CANONICAL_PYTHON,
        "valid": not errors,
        "errors": errors,
        "repositories": repositories,
    }


def _venv_python(repo: Path) -> Path:
    if os.name == "nt":
        return repo / ".venv" / "Scripts" / "python.exe"
    return repo / ".venv" / "bin" / "python"


def _install_plan(repo: Path, venv_python: Path) -> List[List[str]]:
    plan: List[List[str]] = [
        [str(venv_python), "-m", "pip", "install", "--upgrade", "pip"],
        [str(venv_python), "-m", "pip", "install", "uv"],
    ]
    if (repo / "uv.lock").is_file() and (repo / "pyproject.toml").is_file():
        plan.append([str(venv_python), "-m", "uv", "sync", "--locked", "--python", str(venv_python)])
    elif (repo / "requirements.lock").is_file():
        plan.append([str(venv_python), "-m", "pip", "install", "-r", "requirements.lock"])
    elif (repo / "requirements.txt").is_file():
        plan.append([str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"])
    elif (repo / "pyproject.toml").is_file():
        plan.append([str(venv_python), "-m", "pip", "install", "-e", ".[dev]"])
    else:
        raise WorkspaceError(f"no supported dependency declaration in {repo}")
    return plan


def bootstrap_local(
    registry: Registry,
    root: os.PathLike[str] | str,
    *,
    python_executable: str = "python3.11",
    runner: Runner = _subprocess_runner,
) -> List[ActionReceipt]:
    validation = validate_workspace(registry, root)
    structural_errors = [
        item for item in validation["errors"] if "python policy:" not in item
    ]
    if structural_errors:
        raise WorkspaceError("workspace validation failed: " + "; ".join(structural_errors))

    workspace = Path(root).expanduser().resolve()
    receipts: List[ActionReceipt] = []
    for spec in repository_specs(registry):
        repo = workspace / spec.name
        venv = repo / ".venv"
        if not venv.exists():
            runner([python_executable, "-m", "venv", str(venv)], str(repo))
        python = _venv_python(repo)
        for command in _install_plan(repo, python):
            if "--system" in command:
                raise WorkspaceError("local bootstrap attempted a system install")
            runner(command, str(repo))
        receipts.append(ActionReceipt(spec.program_id, "bootstrap", str(repo), "ok"))
    return receipts


def _manifest(repo: Path) -> Mapping[str, Any]:
    path = repo / "federation.json"
    if not path.is_file():
        raise WorkspaceError(f"missing federation manifest: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WorkspaceError(f"invalid federation manifest {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise WorkspaceError(f"federation manifest is not an object: {path}")
    return data


def _production_gate(data: Mapping[str, Any]) -> Tuple[bool, str]:
    readiness = data.get("federation_readiness_gate") or {}
    blockers = readiness.get("blocking_conditions") or []
    if data.get("production_status") != "PRODUCTION":
        return False, "production_status is not PRODUCTION"
    if readiness.get("ready_for_hub_live_execution") is not True:
        return False, "ready_for_hub_live_execution is not true"
    if blockers:
        return False, f"blocking_conditions is non-empty ({len(blockers)})"
    return True, "ready"


def _command_for_mode(data: Mapping[str, Any], mode: str) -> Optional[List[str]]:
    commands = data.get("hub_callable_commands") or {}
    if mode == "test":
        raw = commands.get("export_test") or commands.get("export_canonical")
    elif mode == "production":
        raw = commands.get("export_production")
        if raw is None:
            canonical = commands.get("export_canonical")
            if canonical and "--mode production" in canonical:
                raw = canonical
    elif mode == "live":
        raw = commands.get("live_execution")
    else:
        raise WorkspaceError(f"unsupported execution mode: {mode}")
    return _validate_command(raw) if raw else None


def execute_mode(
    registry: Registry,
    root: os.PathLike[str] | str,
    mode: str,
    *,
    runner: Runner = _subprocess_runner,
) -> List[ActionReceipt]:
    validation = validate_workspace(registry, root)
    if not validation["valid"]:
        raise WorkspaceError("workspace validation failed: " + "; ".join(validation["errors"]))
    workspace = Path(root).expanduser().resolve()
    receipts: List[ActionReceipt] = []
    for producer in registry.producers:
        repo = workspace / producer.repo_name
        data = _manifest(repo)
        if mode in {"production", "live"}:
            allowed, detail = _production_gate(data)
            if not allowed:
                receipts.append(ActionReceipt(producer.program_id, mode, str(repo), "blocked", detail))
                continue
        command = _command_for_mode(data, mode)
        if command is None:
            receipts.append(
                ActionReceipt(producer.program_id, mode, str(repo), "blocked", f"missing safe {mode} command")
            )
            continue
        runner(command, str(repo))
        receipts.append(ActionReceipt(producer.program_id, mode, str(repo), "ok"))
    return receipts


def _emit(receipts: Iterable[ActionReceipt], *, as_json: bool) -> None:
    rows = [asdict(receipt) for receipt in receipts]
    if as_json:
        print(json.dumps(rows, indent=2, sort_keys=True))
        return
    for row in rows:
        suffix = f" — {row['detail']}" if row["detail"] else ""
        print(f"{row['program_id']:16} {row['action']:18} {row['status']:8}{suffix}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prii-workspace")
    parser.add_argument("--registry", default="registry/producers.yaml")
    parser.add_argument("--root", required=True)
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    clone = sub.add_parser("clone")
    clone.add_argument("--depth", type=int, default=1)
    bootstrap = sub.add_parser("bootstrap-local")
    bootstrap.add_argument("--python", default="python3.11")
    sub.add_parser("validate")
    sub.add_parser("export-test")
    sub.add_parser("export-production")
    sub.add_parser("run-live")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    registry = load_registry(args.registry)
    try:
        if args.command == "clone":
            _emit(clone_workspace(registry, args.root, depth=args.depth), as_json=args.json)
            return 0
        if args.command == "validate":
            report = validate_workspace(registry, args.root)
            print(json.dumps(report, indent=2, sort_keys=True))
            return 0 if report["valid"] else 1
        if args.command == "bootstrap-local":
            _emit(
                bootstrap_local(registry, args.root, python_executable=args.python),
                as_json=args.json,
            )
            return 0
        mode = {
            "export-test": "test",
            "export-production": "production",
            "run-live": "live",
        }[args.command]
        receipts = execute_mode(registry, args.root, mode)
        _emit(receipts, as_json=args.json)
        return 0 if all(receipt.status == "ok" for receipt in receipts) else 1
    except WorkspaceError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
