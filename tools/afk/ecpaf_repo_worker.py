#!/usr/bin/env python3
"""ECPAF-V2.2 bounded repository-change worker.

Executes predeclared, byte-pinned source edits in isolated sparse worktrees.
Only creates new draft pull requests; no protected merges or deployments.
Persistent exactly-once intent through SQLite operations and GitHub reconciliation.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "writer-ledger.sqlite3"
LOCK = ROOT / "writer.lock"
WORK_ROOT = Path.home() / "Developer" / "worktrees"
REPO_ROOT = Path.home() / "Developer"
ALLOWED = frozenset(
    {
        "thehub-pr",
        "spiderweb-pr",
        "skywatcher-pr",
        "ovnis-pr",
        "aguayluz-pr",
        "moneysweep-pr",
        "centinelas-pr",
        "mucaro-ai",
    }
)
MIN_FREE_BYTES = 2 * (1024**3)
MAX_BYTES_PER_FILE = 300_000
MAX_FILES_PER_TASK = 15


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def encoding(value) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode()


def hashbytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def command(args: list[str], cwd: Path | None = None, timeout=55) -> str:
    result = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GH_PAGER": "cat"},
    )
    require(
        result.returncode == 0,
        f"COMMAND_FAILED exit={result.returncode}, command={args[0]} {args[1] if len(args) > 1 else ''}; stderr={result.stderr[:220]}",
    )
    return result.stdout.strip()


def github(path: str) -> dict:
    return json.loads(command(["/usr/local/bin/gh", "api", path], timeout=45))


def connection() -> sqlite3.Connection:
    conn = sqlite3.connect(STATE, timeout=15, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS work (id TEXT PRIMARY KEY, state TEXT NOT NULL, baseline TEXT NOT NULL, branch TEXT NOT NULL, started TEXT NOT NULL, updated TEXT NOT NULL, receipt TEXT, result TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, work_id TEXT, state TEXT, evidence TEXT)"
    )
    return conn


def entry(conn, task_id: str, state: str, info: dict) -> str:
    data = encoding({"task_id": task_id, "at": now(), "state": state, "info": info})
    digest = hashbytes(data)
    out = ROOT / "receipts" / f"{digest}.json"
    out.parent.mkdir(exist_ok=True)
    if not out.exists():
        tmp = ROOT / "receipts" / f".{digest}.{os.getpid()}.tmp"
        with tmp.open("xb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, out)
    require(hashbytes(out.read_bytes()) == digest, "INTEGRITY_FAILURE receipt")
    conn.execute(
        "INSERT INTO events(at,work_id,state,evidence) VALUES (?,?,?,?)",
        (now(), task_id, state, digest),
    )
    conn.execute(
        "UPDATE work SET state=?,updated=?,receipt=?,result=? WHERE id=?",
        (state, now(), digest, json.dumps(info, sort_keys=True), task_id),
    )
    return digest


def validate_path(name: str) -> str:
    require(isinstance(name, str) and name and not name.startswith("/"), "invalid path")
    parts = PurePosixPath(name).parts
    require(
        len(parts) > 1 and all(x not in (".", "..", "") for x in parts),
        "unsafe relative path",
    )
    require(
        parts[0] in ("scripts", "tests", "docs", "tools"),
        "path outside bounded source roots",
    )
    require(
        not any(x.startswith(".git") or x == "__pycache__" for x in parts),
        "protected path",
    )
    require(name.endswith((".py", ".md", ".json", ".txt")), "unsupported file suffix")
    return name


def decode_edit(e: dict):
    require(
        set(e) == {"path", "before_sha256", "after_sha256", "content_b64"},
        "unexpected edit fields",
    )
    path = validate_path(e["path"])
    require(
        e["before_sha256"] is None or re.fullmatch(r"[0-9a-f]{64}", e["before_sha256"]),
        "bad before hash",
    )
    require(
        isinstance(e["after_sha256"], str)
        and re.fullmatch(r"[0-9a-f]{64}", e["after_sha256"]),
        "bad after hash",
    )
    data = base64.b64decode(e["content_b64"], validate=True)
    require(0 < len(data) <= MAX_BYTES_PER_FILE, "content size out of bounds")
    require(hashbytes(data) == e["after_sha256"], "declared data hash mismatch")
    return path, data


def validate(task: dict):
    expected = {
        "schema",
        "id",
        "repository",
        "base_sha",
        "branch",
        "title",
        "description",
        "authorization",
        "mode",
        "edits",
    }
    require(set(task) == expected, "unexpected task fields")
    require(
        task["schema"] == "ecpaf-v2.2-repo-task/1"
        and task["mode"] == "DRAFT_PR_ONLY"
        and task["authorization"] == "AI_AUTO",
        "nonauthorized task mode",
    )
    require(
        task["repository"] in ALLOWED, "repository outside owner-approved federation"
    )
    require(
        isinstance(task["id"], str)
        and re.fullmatch(r"[a-z0-9][a-z0-9-]{6,58}", task["id"]),
        "bad task ID",
    )
    require(
        isinstance(task["base_sha"], str)
        and re.fullmatch(r"[0-9a-f]{40}", task["base_sha"]),
        "nonexact baseline",
    )
    require(
        isinstance(task["branch"], str)
        and re.fullmatch(r"feat/ecpaf-v22-[a-z0-9-]{6,65}", task["branch"]),
        "branch not bounded",
    )
    require(
        isinstance(task["title"], str) and 6 <= len(task["title"]) <= 130, "bad title"
    )
    require(
        isinstance(task["description"], str) and 20 <= len(task["description"]) <= 3000,
        "bad description",
    )
    edits = task["edits"]
    require(
        isinstance(edits, list) and 1 <= len(edits) <= MAX_FILES_PER_TASK,
        "bad edit denominator",
    )
    paths = [decode_edit(e)[0] for e in edits]
    require(len(paths) == len(set(paths)), "duplicate edit path")
    return paths


def remote_branch(repo, branch):
    # A missing branch is normal only before operation reservation.
    q = subprocess.run(
        ["/usr/local/bin/gh", "api", f"repos/jotaele44/{repo}/git/ref/heads/{branch}"],
        capture_output=True,
        text=True,
        timeout=35,
    )
    if q.returncode:
        require(
            "404" in q.stderr or "Not Found" in q.stderr,
            "unverified remote branch state",
        )
        return None
    return json.loads(q.stdout)["object"]["sha"]


def reconcile(conn, task):
    repo = task["repository"]
    branch = task["branch"]
    existing = conn.execute(
        "SELECT state,receipt FROM work WHERE id=?", (task["id"],)
    ).fetchone()
    if not existing:
        require(remote_branch(repo, branch) is None, "external branch name collision")
        return None
    if existing[0] == "DONE":
        data = github(
            f"repos/jotaele44/{repo}/pulls?state=all&head=jotaele44:{branch}&per_page=100"
        )
        match = [
            p
            for p in data
            if p["head"]["ref"] == branch and p["head"]["repo"]["name"] == repo
        ]
        require(match, "INTEGRITY_FAILURE completed task PR missing from GitHub")
        return {
            "state": "DONE",
            "pull_request": match[0]["html_url"],
            "receipt": existing[1],
        }
    # PREPARED/ERROR states are intentionally never replayed by this version.
    # A partial push or draft PR needs exact remote effects reconciled by a separate authorized step.
    return {
        "state": "RECONCILIATION_REQUIRED",
        "prior_state": existing[0],
        "receipt": existing[1],
    }


def execute(conn, task):
    paths = validate(task)
    tid = task["id"]
    repo = task["repository"]
    branch = task["branch"]
    prior = reconcile(conn, task)
    if prior:
        return prior
    require(
        shutil.disk_usage(Path.home()).free >= MIN_FREE_BYTES,
        "RESOURCE_EXHAUSTED low disk reserve",
    )
    current = github(f"repos/jotaele44/{repo}/commits/main")["sha"]
    require(current == task["base_sha"], "INTEGRITY_BLOCKED repository main advanced")
    base = REPO_ROOT / repo
    require(base.is_dir() and (base / ".git").exists(), "local repository unavailable")
    require(
        command(["git", "-C", str(base), "rev-parse", "origin/main"]) == current,
        "local origin/main stale",
    )
    require(
        command(["git", "-C", str(base), "status", "--porcelain"]) == "",
        "primary repository dirty",
    )
    directory = WORK_ROOT / f"afk-v22-{tid}"
    require(not directory.exists(), "unclassified existing worktree")
    conn.execute(
        "INSERT INTO work(id,state,baseline,branch,started,updated) VALUES (?,?,?,?,?,?)",
        (tid, "PREPARED", current, branch, now(), now()),
    )
    entry(
        conn,
        tid,
        "PREPARED",
        {"repository": repo, "base_sha": current, "branch": branch, "paths": paths},
    )
    # No implicit retries after PREPARED; remote writes require reconciliation.
    try:
        WORK_ROOT.mkdir(parents=True, exist_ok=True)
        command(
            [
                "git",
                "-C",
                str(base),
                "worktree",
                "add",
                "--detach",
                "--no-checkout",
                str(directory),
                current,
            ],
            timeout=65,
        )
        command(["git", "-C", str(directory), "sparse-checkout", "init", "--no-cone"])
        command(["git", "-C", str(directory), "sparse-checkout", "set", *paths])
        command(["git", "-C", str(directory), "checkout", "-f", "HEAD"], timeout=65)
        for e in task["edits"]:
            path, data = decode_edit(e)
            target = directory / path
            require(
                not target.is_symlink()
                and not any(
                    (directory / Path(*PurePosixPath(path).parts[:i])).is_symlink()
                    for i in range(1, len(PurePosixPath(path).parts))
                ),
                "symlink path",
            )
            if e["before_sha256"] is None:
                require(not target.exists(), "expected new file")
            else:
                require(
                    target.is_file()
                    and hashbytes(target.read_bytes()) == e["before_sha256"],
                    "before content mismatch",
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        command(["git", "-C", str(directory), "add", "--", *paths])
        command(["git", "-C", str(directory), "diff", "--cached", "--check"])
        require(
            command(
                ["git", "-C", str(directory), "diff", "--cached", "--name-only"]
            ).splitlines()
            == sorted(paths)
            or set(
                command(
                    ["git", "-C", str(directory), "diff", "--cached", "--name-only"]
                ).splitlines()
            )
            == set(paths),
            "changes outside declared paths",
        )
        command(
            [
                "git",
                "-C",
                str(directory),
                "-c",
                "user.name=Jotaele44",
                "-c",
                "user.email=jotaele44@users.noreply.github.com",
                "commit",
                "-m",
                task["title"],
            ],
            timeout=50,
        )
        commit = command(["git", "-C", str(directory), "rev-parse", "HEAD"])
        require(
            remote_branch(repo, branch) is None, "remote branch collision before push"
        )
        entry(
            conn,
            tid,
            "COMMITTED",
            {"commit": commit, "baseline": current, "branch": branch},
        )
        command(
            [
                "git",
                "-C",
                str(directory),
                "push",
                "origin",
                "HEAD:refs/heads/" + branch,
            ],
            timeout=90,
        )
        require(remote_branch(repo, branch) == commit, "remote push identity mismatch")
        entry(conn, tid, "PUSHED", {"commit": commit, "branch": branch})
        command(
            [
                "/usr/local/bin/gh",
                "pr",
                "create",
                "--repo",
                "jotaele44/" + repo,
                "--base",
                "main",
                "--head",
                branch,
                "--draft",
                "--title",
                task["title"],
                "--body",
                task["description"],
            ],
            timeout=85,
        )
        prlist = github(
            f"repos/jotaele44/{repo}/pulls?head=jotaele44:{branch}&state=open&per_page=100"
        )
        pr = next(
            (p for p in prlist if p["head"]["sha"] == commit and p["draft"]), None
        )
        require(pr is not None, "new draft PR not verified")
        receipt = entry(
            conn,
            tid,
            "DONE",
            {
                "repo": repo,
                "baseline": current,
                "commit": commit,
                "branch": branch,
                "draft_pr": pr["html_url"],
                "protected_operations": [],
            },
        )
        # Cleanup only if clean, and remote branch & PR verify the commit.
        require(
            command(["git", "-C", str(directory), "status", "--porcelain"]) == "",
            "worktree unexpectedly dirty",
        )
        command(
            ["git", "-C", str(base), "worktree", "remove", str(directory)], timeout=40
        )
        return {
            "state": "DONE",
            "pr": pr["html_url"],
            "commit": commit,
            "receipt": receipt,
        }
    except Exception as exc:
        entry(
            conn,
            tid,
            "RECONCILIATION_REQUIRED",
            {"error": str(exc)[:350], "worktree": str(directory)},
        )
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True, type=Path)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    raw = args.task.read_bytes()
    task = json.loads(raw)
    paths = validate(task)
    if args.plan_only:
        print(
            json.dumps(
                {
                    "state": "PLAN_VALID",
                    "task": task["id"],
                    "files": paths,
                    "task_sha256": hashbytes(raw),
                }
            )
        )
        return 0
    ROOT.mkdir(parents=True, exist_ok=True)
    with LOCK.open("a+") as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("WORKER_ALREADY_RUNNING")
            return 2
        conn = connection()
        try:
            result = execute(conn, task)
            print(json.dumps(result, sort_keys=True))
            return 0 if result["state"] == "DONE" else 3
        except Exception as exc:
            print(
                json.dumps({"state": "BLOCKED_OR_FAILED", "detail": str(exc)[:350]}),
                file=sys.stderr,
            )
            return 4
        finally:
            conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
