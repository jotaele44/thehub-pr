#!/usr/bin/env python3
"""Audit setup and startup completion for the seven-repo federation.

This runner is receipt-first: each command writes a log, each repository is
classified exactly once, and setup/startup completion is kept separate from
producer live-readiness or product-completion blockers.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ORDER = [
    "aguayluz-pr",
    "centinelas-pr",
    "moneysweep-pr",
    "ovnis-pr",
    "skywatcher-pr",
    "spiderweb-pr",
    "thehub-pr",
]

PRODUCT_COMPLETION_BLOCKERS = {
    "moneysweep-pr": "MANIFEST_READY_FOR_HUB_LIVE_EXECUTION_FALSE",
    "skywatcher-pr": "MANIFEST_READY_FOR_HUB_LIVE_EXECUTION_FALSE",
}

SETUP_REQUIRED = {"setup", "test_suite", "export_canonical", "startup_smoke"}
DEFAULT_TIMEOUT = 600


@dataclass
class CommandResult:
    name: str
    command: str
    state: str
    exit_code: int | None
    elapsed_seconds: float
    log_path: str | None
    reason: str | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_capture(args: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)
    return proc.returncode, proc.stdout, proc.stderr


def git(cwd: Path, *args: str) -> str:
    code, out, err = run_capture(["git", *args], cwd)
    if code != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}: {err.strip()}")
    return out.strip()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def env_presence(names: list[str]) -> dict[str, bool]:
    return {name: bool(os.environ.get(name)) for name in names}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def shared_pythonpath(source_root: Path, existing: str | None = None) -> str:
    paths = [
        source_root / "thehub-pr" / "packages" / "prii_maintenance" / "src",
        source_root / "thehub-pr" / "packages" / "prii_export_utils" / "src",
    ]
    values = [str(path) for path in paths if path.exists()]
    if existing:
        values.append(existing)
    return os.pathsep.join(values)


def run_command(
    *,
    name: str,
    command: str,
    cwd: Path,
    log_dir: Path,
    timeout: int,
    env_extra: dict[str, str] | None = None,
) -> CommandResult:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{name}.log"
    started = time.monotonic()
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    with log_path.open("w") as log:
        log.write(f"$ {command}\n")
        log.write(f"# cwd: {cwd}\n")
        log.write(f"# started_utc: {utc_now()}\n\n")
        try:
            proc = subprocess.run(
                command,
                cwd=cwd,
                shell=True,
                text=True,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
                env=env,
            )
            state = "PASS" if proc.returncode == 0 else "FAIL"
            return CommandResult(
                name,
                command,
                state,
                proc.returncode,
                round(time.monotonic() - started, 3),
                str(log_path),
            )
        except subprocess.TimeoutExpired:
            return CommandResult(
                name,
                command,
                "BLOCKED",
                None,
                round(time.monotonic() - started, 3),
                str(log_path),
                f"TIMEOUT:{timeout}s",
            )


def skipped(name: str, reason: str, command: str = "") -> CommandResult:
    return CommandResult(name, command, "SKIP_WITH_REASON", None, 0.0, None, reason)


def primary_launcher(repo_id: str, repo_path: Path) -> Path | None:
    short = repo_id.removesuffix("-pr").upper()
    candidates = [
        repo_path / f"PRII-{short}.command",
        repo_path / f"PRII-{short}.sh",
        repo_path / "PRII-THEHUB.command",
        repo_path / "PRII-FEDERATION.command",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    command_files = sorted(repo_path.glob("*.command"))
    return command_files[0] if command_files else None


def startup_smoke_command(repo_id: str, repo_path: Path) -> tuple[str, str]:
    if repo_id == "thehub-pr":
        return (
            "startup_smoke",
            "python3 -m py_compile desktop/launch.py desktop/app_server.py server/backend/main.py "
            "&& (cd server/frontend && npm run build)",
        )
    launcher = primary_launcher(repo_id, repo_path)
    if launcher is None:
        return ("startup_smoke", "python3 -c \"raise SystemExit('no launcher found')\"")
    return ("startup_smoke", f"bash -n {shlex.quote(str(launcher))}")


def thehub_command_plan(audit_tmp: Path, run_setup: bool) -> list[tuple[str, str | None, str]]:
    aggregate_out = audit_tmp / "thehub-aggregate"
    setup = "python3 -m py_compile scripts/startup_completion_audit.py desktop/launch.py desktop/app_server.py server/backend/main.py"
    tests = (
        "PYTHONPATH=src python3 -m pytest -q "
        "tests/test_startup_completion_audit.py "
        "tests/test_federation_status.py "
        "tests/test_build_hub_fixture.py"
    )
    export = f"PYTHONPATH=src python3 -m hub aggregate --root .. --out {shlex.quote(str(aggregate_out))}"
    plan: list[tuple[str, str | None, str]] = [
        ("setup", setup if run_setup else None, "setup skipped by audit policy; use --run-setup to execute"),
        ("test_suite", tests, ""),
        ("export_canonical", export, ""),
    ]
    startup_name, startup_cmd = startup_smoke_command("thehub-pr", Path.cwd())
    plan.append((startup_name, startup_cmd, ""))
    return plan


def producer_command_plan(repo_id: str, repo_path: Path, manifest: dict[str, Any], run_setup: bool) -> list[tuple[str, str | None, str]]:
    commands = manifest.get("hub_callable_commands") or {}
    plan: list[tuple[str, str | None, str]] = [
        ("setup", commands.get("setup") if run_setup else None, "setup skipped by audit policy; use --run-setup to execute")
    ]
    for name in ("validation_gates", "validate_grid", "validate_ledgers", "validate_schemas", "validate_export"):
        if commands.get(name):
            plan.append((name, commands[name], ""))
            break
    plan.append(("test_suite", commands.get("test_suite"), "test command not declared"))
    plan.append(("export_canonical", commands.get("export_canonical"), "export command not declared"))
    startup_name, startup_cmd = startup_smoke_command(repo_id, repo_path)
    plan.append((startup_name, startup_cmd, ""))
    return plan


def command_plan(
    repo_id: str,
    repo_path: Path,
    manifest: dict[str, Any],
    run_setup: bool,
    audit_tmp: Path,
) -> list[tuple[str, str | None, str]]:
    if repo_id == "thehub-pr":
        return thehub_command_plan(audit_tmp, run_setup)
    return producer_command_plan(repo_id, repo_path, manifest, run_setup)


def classify_startup_setup(command_results: list[CommandResult]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    failing = [result for result in command_results if result.state in {"FAIL", "BLOCKED"}]
    if failing:
        reasons.extend(f"{result.name}:{result.state}" for result in failing)
        return "FAIL", reasons
    skipped_required = [
        result for result in command_results if result.name in SETUP_REQUIRED and result.state == "SKIP_WITH_REASON"
    ]
    if skipped_required:
        reasons.extend(f"{result.name}:{result.reason}" for result in skipped_required)
        return "BLOCKED", reasons
    return "STARTUP_SETUP_COMPLETE", []


def classify_product_completion(
    repo_id: str,
    ready_for_live: bool | None,
    manifest_blockers: list[str],
    startup_setup_state: str,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if startup_setup_state != "STARTUP_SETUP_COMPLETE":
        reasons.append(f"startup_setup_state:{startup_setup_state}")
    reasons.extend(manifest_blockers)
    if ready_for_live is False:
        reasons.append(PRODUCT_COMPLETION_BLOCKERS.get(repo_id, "MANIFEST_READY_FOR_HUB_LIVE_EXECUTION_FALSE"))
    if reasons:
        return "BLOCKED_FOR_PRODUCT_COMPLETION", reasons
    return "PRODUCT_COMPLETE", []


def classify_repo(
    repo_id: str,
    ready_for_live: bool | None,
    blockers: list[str],
    command_results: list[CommandResult],
) -> tuple[str, list[str], str, list[str]]:
    startup_state, startup_blockers = classify_startup_setup(command_results)
    product_state, product_blockers = classify_product_completion(repo_id, ready_for_live, blockers, startup_state)
    return startup_state, startup_blockers, product_state, product_blockers


def audit_repo(
    *,
    repo_id: str,
    repo_path: Path,
    manifest: dict[str, Any],
    out_dir: Path,
    timeout: int,
    run_setup: bool,
    source_root: Path,
) -> dict[str, Any]:
    head_sha = git(repo_path, "rev-parse", "HEAD")
    branch = git(repo_path, "rev-parse", "--abbrev-ref", "HEAD")
    status = git(repo_path, "status", "--porcelain=v1")
    remote_sha = ""
    try:
        remote_sha = git(repo_path, "rev-parse", "origin/main")
    except RuntimeError:
        pass
    readiness = manifest.get("federation_readiness_gate") or {}
    blockers = list(readiness.get("blocking_conditions") or [])
    required_env = list((manifest.get("source_truth") or {}).get("runtime_required_keys") or [])
    log_dir = out_dir / "logs" / repo_id
    audit_tmp = out_dir / "tmp" / repo_id
    audit_tmp.mkdir(parents=True, exist_ok=True)
    env_extra = {"PYTHONPATH": shared_pythonpath(source_root, os.environ.get("PYTHONPATH"))}
    command_results: list[CommandResult] = []
    for name, command, skip_reason in command_plan(repo_id, repo_path, manifest, run_setup, audit_tmp):
        if not command:
            command_results.append(skipped(name, skip_reason))
            continue
        command_results.append(
            run_command(name=name, command=command, cwd=repo_path, log_dir=log_dir, timeout=timeout, env_extra=env_extra)
        )
    startup_state, startup_blockers, product_state, product_blockers = classify_repo(
        repo_id,
        readiness.get("ready_for_hub_live_execution"),
        blockers,
        command_results,
    )
    return {
        "repo_id": repo_id,
        "path": str(repo_path),
        "branch": branch,
        "head_sha": head_sha,
        "remote_main_sha": remote_sha,
        "worktree_clean": not bool(status),
        "dirty_status": status.splitlines(),
        "manifest_present": bool(manifest),
        "production_status": manifest.get("production_status"),
        "ready_for_hub_discovery": readiness.get("ready_for_hub_discovery"),
        "ready_for_hub_live_execution": readiness.get("ready_for_hub_live_execution"),
        "required_env": env_presence(required_env),
        "command_results": [result.__dict__ for result in command_results],
        "startup_setup_state": startup_state,
        "startup_setup_blockers": startup_blockers,
        "product_completion_state": product_state,
        "product_completion_blockers": product_blockers,
        "completion_state": startup_state,
        "blockers": startup_blockers,
    }


def add_worktree(source_repo: Path, workspace: Path, repo_id: str) -> Path:
    target = workspace / repo_id
    if target.exists():
        return target
    git(source_repo, "fetch", "origin", "main")
    code, out, err = run_capture(["git", "worktree", "add", "--detach", str(target), "origin/main"], source_repo)
    if code != 0:
        raise RuntimeError(f"worktree add failed for {repo_id}: {err or out}")
    return target


def build_summary(
    run_id: str,
    out_dir: Path,
    repo_results: list[dict[str, Any]],
    source_root: Path,
    audit_workspace: Path,
) -> dict[str, Any]:
    setup_counts: dict[str, int] = {}
    product_counts: dict[str, int] = {}
    for result in repo_results:
        setup_state = result["startup_setup_state"]
        product_state = result["product_completion_state"]
        setup_counts[setup_state] = setup_counts.get(setup_state, 0) + 1
        product_counts[product_state] = product_counts.get(product_state, 0) + 1
    classified = sum(setup_counts.values())
    startup_certification = "PASS" if setup_counts == {"STARTUP_SETUP_COMPLETE": len(REPO_ORDER)} else "PROVISIONAL"
    product_certification = "PASS" if product_counts == {"PRODUCT_COMPLETE": len(REPO_ORDER)} else "PROVISIONAL"
    return {
        "schema_version": "startup_completion_audit.v2",
        "run_id": run_id,
        "generated_utc": utc_now(),
        "source_root": str(source_root),
        "audit_workspace": str(audit_workspace),
        "tooling": {
            "skill_selector": "UNAVAILABLE",
            "lumen_status": "LUMEN_UNAVAILABLE_OR_UNHEALTHY",
            "search_exhaustion": "BOUNDED_LOCAL_INSPECTION_ONLY",
        },
        "startup_setup_certification": startup_certification,
        "product_completion_certification": product_certification,
        "certification": startup_certification,
        "arithmetic": {
            "total": len(REPO_ORDER),
            "classified": classified,
            "counts": setup_counts,
            "closed": classified == len(REPO_ORDER),
        },
        "product_arithmetic": {
            "total": len(REPO_ORDER),
            "classified": sum(product_counts.values()),
            "counts": product_counts,
            "closed": sum(product_counts.values()) == len(REPO_ORDER),
        },
        "repositories": repo_results,
        "receipt_paths": {
            "json": str(out_dir / "startup_completion_audit.json"),
            "markdown": str(out_dir / "STARTUP_COMPLETION_AUDIT.md"),
        },
    }


def write_markdown(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Federation Startup Completion Audit",
        "",
        f"- Generated UTC: `{summary['generated_utc']}`",
        f"- Run ID: `{summary['run_id']}`",
        f"- Startup/setup certification: `{summary['startup_setup_certification']}`",
        f"- Product completion certification: `{summary['product_completion_certification']}`",
        f"- Startup/setup arithmetic: `{summary['arithmetic']['classified']}={summary['arithmetic']['total']}`",
        f"- Lumen: `{summary['tooling']['lumen_status']}`",
        f"- Deferred Skill selector: `{summary['tooling']['skill_selector']}`",
        "",
        "## Repository Results",
        "",
        "| Repo | SHA | Startup/setup | Product completion | Live Ready | Setup | Tests | Export | Startup |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for repo in summary["repositories"]:
        commands = {result["name"]: result for result in repo["command_results"]}
        lines.append(
            "| {repo} | `{sha}` | `{setup_state}` | `{product_state}` | `{live}` | `{setup}` | `{tests}` | `{export}` | `{startup}` |".format(
                repo=repo["repo_id"],
                sha=repo["head_sha"][:12],
                setup_state=repo["startup_setup_state"],
                product_state=repo["product_completion_state"],
                live=repo["ready_for_hub_live_execution"],
                setup=commands.get("setup", {}).get("state", "SKIP_WITH_REASON"),
                tests=commands.get("test_suite", {}).get("state", "SKIP_WITH_REASON"),
                export=commands.get("export_canonical", {}).get("state", "SKIP_WITH_REASON"),
                startup=commands.get("startup_smoke", {}).get("state", "SKIP_WITH_REASON"),
            )
        )
    lines.extend(["", "## Startup/Setup Blockers", ""])
    for repo in summary["repositories"]:
        if repo["startup_setup_state"] != "STARTUP_SETUP_COMPLETE":
            lines.append(
                f"- `{repo['repo_id']}`: `{repo['startup_setup_state']}` - "
                f"{', '.join(repo['startup_setup_blockers']) or 'no blocker text'}"
            )
    lines.extend(["", "## Product Completion Blockers", ""])
    for repo in summary["repositories"]:
        if repo["product_completion_state"] != "PRODUCT_COMPLETE":
            lines.append(
                f"- `{repo['repo_id']}`: `{repo['product_completion_state']}` - "
                f"{', '.join(repo['product_completion_blockers']) or 'no blocker text'}"
            )
    path.write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="..", help="Directory holding federation repo checkouts.")
    parser.add_argument("--out", default="", help="Receipt directory. Defaults to reports/startup-audit/<run-id>.")
    parser.add_argument("--workspace", default="", help="Audit worktree workspace. Defaults to a temp directory.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--run-setup", action="store_true", help="Execute setup commands. Default records setup as skipped.")
    args = parser.parse_args(argv)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    here = Path(__file__).resolve().parents[1]
    source_root = (here / args.root).resolve()
    out_dir = Path(args.out) if args.out else here / "reports" / "startup-audit" / run_id
    if not out_dir.is_absolute():
        out_dir = (here / out_dir).resolve()
    if args.workspace:
        audit_workspace = Path(args.workspace).resolve()
        audit_workspace.mkdir(parents=True, exist_ok=True)
    else:
        audit_workspace = Path(tempfile.mkdtemp(prefix=f"startup-audit-{run_id}-"))

    repo_results: list[dict[str, Any]] = []
    for repo_id in REPO_ORDER:
        source_repo = source_root / repo_id
        if repo_id == "thehub-pr":
            repo_path = here
            manifest = {}
        else:
            repo_path = add_worktree(source_repo, audit_workspace, repo_id)
            manifest = load_json(repo_path / "federation.json")
        repo_results.append(
            audit_repo(
                repo_id=repo_id,
                repo_path=repo_path,
                manifest=manifest,
                out_dir=out_dir,
                timeout=args.timeout,
                run_setup=args.run_setup,
                source_root=source_root,
            )
        )

    summary = build_summary(run_id, out_dir, repo_results, source_root, audit_workspace)
    write_json(out_dir / "startup_completion_audit.json", summary)
    write_markdown(out_dir / "STARTUP_COMPLETION_AUDIT.md", summary)
    print(
        json.dumps(
            {
                "run_id": run_id,
                "startup_setup_certification": summary["startup_setup_certification"],
                "product_completion_certification": summary["product_completion_certification"],
                "arithmetic": summary["arithmetic"],
                "product_arithmetic": summary["product_arithmetic"],
                "receipt": str(out_dir / "startup_completion_audit.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if summary["arithmetic"]["closed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
