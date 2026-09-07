#!/usr/bin/env python3
"""Run the federation completion assessment as one restartable receipt bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ORDER = [
    "aguayluz-pr",
    "centinelas-pr",
    "moneysweep-pr",
    "ovnis-pr-actual",
    "skywatcher-pr",
    "spiderweb-pr",
    "thehub-pr",
]


@dataclass
class CommandReceipt:
    name: str
    command: list[str]
    exit_code: int
    log_path: str


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_capture(args: list[str], cwd: Path, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, check=False)


def run_logged(name: str, args: list[str], cwd: Path, log_dir: Path, *, env: dict[str, str] | None = None) -> CommandReceipt:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{name}.log"
    proc = run_capture(args, cwd, env=env)
    log_path.write_text(
        "\n".join(
            [
                "$ " + " ".join(args),
                f"# cwd: {cwd}",
                f"# exit_code: {proc.returncode}",
                "",
                proc.stdout,
                proc.stderr,
            ]
        )
    )
    return CommandReceipt(name=name, command=args, exit_code=proc.returncode, log_path=str(log_path))


def git(cwd: Path, *args: str) -> str:
    proc = run_capture(["git", *args], cwd)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def repo_snapshot(root: Path, repo_id: str) -> dict[str, Any]:
    path = root / repo_id
    status = git(path, "status", "--porcelain=v1")
    return {
        "repo_id": repo_id,
        "path": str(path),
        "remote_url": git(path, "remote", "get-url", "origin"),
        "branch": git(path, "branch", "--show-current"),
        "head_sha": git(path, "rev-parse", "HEAD"),
        "origin_main_sha": git(path, "rev-parse", "origin/main"),
        "ahead_behind": git(path, "rev-list", "--left-right", "--count", "HEAD...origin/main"),
        "dirty_count": len([line for line in status.splitlines() if line]),
        "dirty_status": status.splitlines(),
    }


def parse_remote_gate(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    by_repo: dict[str, dict[str, int]] = {}
    for row in payload.get("rows", []):
        repo = row["repository"]
        state = row["state"]
        by_repo.setdefault(repo, {})
        by_repo[repo][state] = by_repo[repo].get(state, 0) + 1
    return {
        "certification": payload.get("certification"),
        "open_pr_denominator": payload.get("open_pr_denominator"),
        "counts": payload.get("counts", {}),
        "actionable_counts": payload.get("actionable_counts", {}),
        "open_pr_denominator_complete": payload.get("open_pr_denominator_complete"),
        "audit_truncated": payload.get("audit_truncated"),
        "errors": payload.get("errors", []),
        "by_repo": by_repo,
    }


def parse_startup_audit(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    return {
        "startup_setup_certification": payload.get("startup_setup_certification"),
        "product_completion_certification": payload.get("product_completion_certification"),
        "arithmetic": payload.get("arithmetic", {}),
        "product_arithmetic": payload.get("product_arithmetic", {}),
        "code_completion_arithmetic": payload.get("code_completion_arithmetic", {}),
        "repositories": [
            {
                "repo_id": repo.get("repo_id"),
                "code_completion_state": repo.get("code_completion_state"),
                "startup_setup_state": repo.get("startup_setup_state"),
                "product_completion_state": repo.get("product_completion_state"),
                "production_status": repo.get("production_status"),
                "ready_for_hub_live_execution": repo.get("ready_for_hub_live_execution"),
                "code_completion_blockers": repo.get("code_completion_blockers", []),
                "startup_setup_blockers": repo.get("startup_setup_blockers", []),
                "product_completion_blockers": repo.get("product_completion_blockers", []),
            }
            for repo in payload.get("repositories", [])
        ],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def write_implementation_plan(path: Path, summary: dict[str, Any]) -> None:
    remote = summary.get("remote_gate", {})
    startup = summary.get("startup_audit", {})
    lines = [
        "# Federation Completion Implementation Plan",
        "",
        f"- Generated UTC: `{summary['generated_utc']}`",
        f"- Run ID: `{summary['run_id']}`",
        f"- Scope: `7 federation repos + open PR remote gate`",
        f"- Certification: `{summary['certification']}`",
        f"- Remote PR denominator: `{remote.get('open_pr_denominator')}`",
        f"- Remote certification: `{remote.get('certification')}`",
        f"- Startup/setup certification: `{startup.get('startup_setup_certification')}`",
        f"- Product completion certification: `{startup.get('product_completion_certification')}`",
        "- Code completion language: `CODE_COMPLETE_CANDIDATE is not source-certified or product-certified.`",
        "",
        "## Gates",
        "",
        f"- Remote PR arithmetic: `{remote.get('counts', {})}`",
        f"- Remote actionable residue: `{remote.get('actionable_counts', {})}`",
        f"- Code-completion arithmetic: `{startup.get('code_completion_arithmetic', {}).get('counts', {})}`",
        f"- Startup/setup arithmetic: `{startup.get('arithmetic', {}).get('counts', {})}`",
        f"- Product arithmetic: `{startup.get('product_arithmetic', {}).get('counts', {})}`",
        "",
        "## VECTOR_A Current Implementation Order",
        "",
    ]
    repositories = startup.get("repositories", [])
    incomplete = [repo for repo in repositories if repo.get("code_completion_state") != "CODE_COMPLETE_CANDIDATE"]
    candidates = [repo for repo in repositories if repo.get("code_completion_state") == "CODE_COMPLETE_CANDIDATE"]
    for repo in incomplete:
        lines.append(
            "- `{repo}`: fix code gates `{code_state}` before source/product certification; blockers `{blockers}`.".format(
                repo=repo.get("repo_id"),
                code_state=repo.get("code_completion_state"),
                blockers=repo.get("code_completion_blockers", []),
            )
        )
    for repo in candidates:
        lines.append(
            "- `{repo}`: code gates are `{code_state}`; run setup/source/product gates before any certification claim; blockers `{blockers}`.".format(
                repo=repo.get("repo_id"),
                code_state=repo.get("code_completion_state"),
                blockers=repo.get("product_completion_blockers", []),
            )
        )
    lines.extend(
        [
            "",
            "## VECTOR_B Deterministic Rerun",
            "",
            "- Reuse `scripts/federation_completion_runner.py` as the single receipt entrypoint.",
            "- Keep `--fail-on-actionable` enabled so remote PR residue cannot silently pass.",
            "- Keep explicit timeout values; timeout exhaustion is `BLOCKED`, not `FAIL` or `PASS`.",
            "",
            "## VECTOR_C Reporting Boundary",
            "",
            "- `CODE_COMPLETE_CANDIDATE` means deterministic code gates passed in this audit.",
            "- `STARTUP_SETUP_COMPLETE` additionally requires setup gates to be executed or explicitly satisfied.",
            "- `PRODUCT_COMPLETE` additionally requires live/source blockers to be closed.",
            "- `CERTIFIED` is not emitted by this runner.",
        ]
    )
    path.write_text("\n".join(lines) + "\n")


def python_alias_env() -> tuple[dict[str, str], str | None]:
    env = os.environ.copy()
    if run_capture(["sh", "-c", "command -v python"], Path.cwd()).returncode == 0:
        return env, None
    shim_dir = Path(tempfile.mkdtemp(prefix="federation-python-shim-"))
    (shim_dir / "python").symlink_to(Path(sys.executable))
    env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
    return env, str(shim_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="..", help="Directory holding the seven federation checkouts.")
    parser.add_argument("--out", default="", help="Receipt directory. Defaults to reports/federation-completion/<run-id>.")
    parser.add_argument("--skip-fetch", action="store_true", help="Use existing remote refs without fetching.")
    parser.add_argument("--startup-timeout", type=int, default=600)
    parser.add_argument("--run-setup", action="store_true")
    parser.add_argument("--fail-on-actionable", action="store_true")
    args = parser.parse_args(argv)

    here = Path(__file__).resolve().parents[1]
    root = (here / args.root).resolve()
    run_id = utc_stamp()
    out_dir = Path(args.out) if args.out else here / "reports" / "federation-completion" / run_id
    if not out_dir.is_absolute():
        out_dir = (here / out_dir).resolve()
    log_dir = out_dir / "logs"

    before = [repo_snapshot(root, repo_id) for repo_id in REPO_ORDER]
    fetch_receipts: list[CommandReceipt] = []
    if not args.skip_fetch:
        for repo_id in REPO_ORDER:
            fetch_receipts.append(
                run_logged("fetch-" + repo_id, ["git", "fetch", "--all", "--prune", "--tags"], root / repo_id, log_dir)
            )
    after = [repo_snapshot(root, repo_id) for repo_id in REPO_ORDER]

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("BLOCKED: GITHUB_TOKEN/GH_TOKEN is required for the remote completion gate")

    remote_ledger = out_dir / "remote-completion-ledger.json"
    remote_command = [
        sys.executable,
        str(here / "scripts" / "federation_completion_gate.py"),
        "--config",
        str(here / "federation" / "completion-gate.json"),
        "--out",
        str(remote_ledger),
    ]
    if args.fail_on_actionable:
        remote_command.append("--fail-on-actionable")
    remote_env = os.environ.copy()
    remote_env["GH_TOKEN"] = token
    remote_receipt = run_logged("remote-completion-gate", remote_command, here, log_dir, env=remote_env)

    startup_dir = out_dir / "startup"
    startup_command = [
        sys.executable,
        str(here / "scripts" / "startup_completion_audit.py"),
        "--root",
        str(root),
        "--out",
        str(startup_dir),
        "--timeout",
        str(args.startup_timeout),
    ]
    if args.run_setup:
        startup_command.append("--run-setup")
    startup_env, python_shim_dir = python_alias_env()
    startup_receipt = run_logged("startup-completion-audit", startup_command, here, log_dir, env=startup_env)
    startup_ledger = startup_dir / "startup_completion_audit.json"

    artifacts = {
        "remote_completion_ledger": str(remote_ledger),
        "startup_completion_ledger": str(startup_ledger),
        "implementation_plan": str(out_dir / "IMPLEMENTATION_PLAN.md"),
        "summary": str(out_dir / "summary.json"),
    }
    artifact_hashes = {
        name: sha256_file(Path(path))
        for name, path in artifacts.items()
        if name != "summary" and Path(path).exists()
    }
    summary = {
        "schema_version": "federation_completion_runner.v1",
        "run_id": run_id,
        "generated_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "root": str(root),
        "tooling": {
            "lumen": "UNAVAILABLE_NOT_EXPOSED",
            "mode": "remote_pr_gate_plus_startup_product_audit",
            "python_shim_dir": python_shim_dir,
        },
        "repo_snapshots_before_fetch": before,
        "repo_snapshots_after_fetch": after,
        "commands": [asdict(receipt) for receipt in [*fetch_receipts, remote_receipt, startup_receipt]],
        "remote_gate": parse_remote_gate(remote_ledger) if remote_ledger.exists() else {"missing": True},
        "startup_audit": parse_startup_audit(startup_ledger) if startup_ledger.exists() else {"missing": True},
        "artifacts": artifacts,
        "artifact_sha256": artifact_hashes,
        "certification": "AUDIT_ONLY",
    }
    write_implementation_plan(Path(artifacts["implementation_plan"]), summary)
    write_json(out_dir / "summary.json", summary)
    print(json.dumps({"summary": str(out_dir / "summary.json"), "certification": "AUDIT_ONLY"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
