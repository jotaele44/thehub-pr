from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(command: list[str], cwd: Path | None = None, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)


def receipt_digest(receipt: dict[str, Any]) -> str:
    payload = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def checkout_one(workspace: Path, repo: dict[str, Any]) -> dict[str, Any]:
    target = workspace / repo["workspace_directory"]
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    remote = f"https://github.com/{repo['repository']}.git"
    steps: list[dict[str, Any]] = []

    commands = [
        ["git", "init", "-q"],
        ["git", "remote", "add", "origin", remote],
        ["git", "-c", "protocol.version=2", "fetch", "--no-tags", "--depth=1", "origin", repo["commit"]],
        ["git", "checkout", "--detach", "FETCH_HEAD"],
    ]
    for command in commands:
        proc = run(command, cwd=target)
        steps.append({"command": command[:3], "returncode": proc.returncode})
        if proc.returncode != 0:
            receipt = {
                "repository": repo["repository"],
                "expected_commit": repo["commit"],
                "success": False,
                "failure_step": command[0:3],
                "steps": steps,
            }
            receipt["receipt_sha256"] = receipt_digest(receipt)
            return receipt

    head = run(["git", "rev-parse", "HEAD"], cwd=target, timeout=15).stdout.strip()
    remote_after = run(["git", "remote", "get-url", "origin"], cwd=target, timeout=15).stdout.strip()
    clean = run(["git", "status", "--porcelain"], cwd=target, timeout=15).stdout.strip() == ""
    success = head == repo["commit"] and remote_after == remote and clean
    receipt = {
        "repository": repo["repository"],
        "workspace_directory": repo["workspace_directory"],
        "expected_commit": repo["commit"],
        "actual_commit": head,
        "remote": remote_after,
        "clean": clean,
        "success": success,
        "steps": steps,
    }
    receipt["receipt_sha256"] = receipt_digest(receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    args.workspace.mkdir(parents=True, exist_ok=True)
    receipts = [checkout_one(args.workspace, repo) for repo in manifest["repositories"]]
    result = {
        "schema_version": "0.2.0",
        "generated_at": utcnow(),
        "repositories_expected": len(receipts),
        "repositories_exact": sum(bool(item["success"]) for item in receipts),
        "receipts": receipts,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"repositories_expected": len(receipts), "repositories_exact": result["repositories_exact"]}))
    return 0 if result["repositories_exact"] == len(receipts) else 2


if __name__ == "__main__":
    raise SystemExit(main())
