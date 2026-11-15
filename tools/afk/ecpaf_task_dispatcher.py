#!/usr/bin/env python3
"""Durable bounded AFK task dispatcher for verified draft-PR-only workers.

No free-form command execution or dynamic authorization. The dispatcher accepts
an exact byte-pinned manifest DAG and one immutable worker executable.
"""

from __future__ import annotations

import argparse
from contextlib import closing
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
DB = ROOT / "dispatcher.sqlite3"
LOCK = ROOT / "dispatcher.lock"
MAX_JOBS = 12


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise RuntimeError(reason)


def init() -> sqlite3.Connection:
    db = sqlite3.connect(DB, timeout=20, isolation_level=None)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.execute(
        "CREATE TABLE IF NOT EXISTS epochs (id TEXT PRIMARY KEY, plan_sha TEXT NOT NULL, status TEXT NOT NULL, created_utc TEXT NOT NULL, heartbeat_utc TEXT, restarts INTEGER DEFAULT 0)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, state TEXT NOT NULL, task_sha TEXT NOT NULL, updated_utc TEXT, details TEXT)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, job_id TEXT, state TEXT, receipt_sha TEXT)"
    )
    return db


def receipt(event: dict) -> str:
    raw = (json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n").encode()
    digest = sha(raw)
    folder = ROOT / "dispatch_receipts"
    folder.mkdir(exist_ok=True)
    output = folder / f"{digest}.json"
    if output.exists():
        require(sha(output.read_bytes()) == digest, "INTEGRITY_FAILURE altered receipt")
        return digest
    tmp = folder / f".{digest}.{os.getpid()}.tmp"
    with tmp.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, output)
    return digest


def note(db, job_id, state, details):
    data = {"job_id": job_id, "state": state, "details": details, "at": utc()}
    digest = receipt(data)
    db.execute(
        "UPDATE jobs SET state=?,updated_utc=?,details=? WHERE id=?",
        (state, utc(), json.dumps(details, sort_keys=True), job_id),
    )
    db.execute(
        "INSERT INTO events(at,job_id,state,receipt_sha) VALUES (?,?,?,?)",
        (utc(), job_id, state, digest),
    )
    return digest


def load_plan(path: Path, worker_path: Path):
    require(path.is_file() and not path.is_symlink(), "invalid plan file")
    raw = path.read_bytes()
    plan = json.loads(raw)
    require(
        set(plan) == {"schema", "epoch_id", "worker_sha256", "jobs"},
        "unexpected plan fields",
    )
    require(plan["schema"] == "ecpaf-v2.2-dispatch/1", "wrong plan schema")
    require(
        re.fullmatch(r"afk-v22-[a-z0-9-]{8,64}", plan["epoch_id"]) is not None,
        "bad epoch ID",
    )
    require(worker_path.is_file() and not worker_path.is_symlink(), "worker missing")
    require(
        sha(worker_path.read_bytes()) == plan["worker_sha256"],
        "INTEGRITY_FAILURE worker source mismatch",
    )
    jobs = plan["jobs"]
    require(
        isinstance(jobs, list) and 1 <= len(jobs) <= MAX_JOBS,
        "unbounded job denominator",
    )
    ids = set()
    for j in jobs:
        require(
            set(j) == {"id", "task_file", "task_sha256", "dependencies"},
            "invalid job schema",
        )
        tid = j["id"]
        require(
            isinstance(tid, str)
            and re.fullmatch(r"[a-z0-9][a-z0-9-]{6,58}", tid) is not None,
            "invalid job ID",
        )
        require(tid not in ids, "duplicate job ID")
        ids.add(tid)
        path_str = j["task_file"]
        require(
            isinstance(path_str, str)
            and re.fullmatch(r"[a-z0-9][a-z0-9-]{6,58}\.json", path_str) is not None,
            "unsafe task filename",
        )
        task = path.parent / path_str
        require(task.is_file() and not task.is_symlink(), "task manifest absent")
        require(
            sha(task.read_bytes()) == j["task_sha256"],
            "INTEGRITY_FAILURE task manifest differs",
        )
        content = json.loads(task.read_bytes())
        require(content["id"] == tid, "manifest/task identity mismatch")
        deps = j["dependencies"]
        require(
            isinstance(deps, list)
            and len(deps) == len(set(deps))
            and all(isinstance(x, str) for x in deps),
            "bad dependencies",
        )
        require(tid not in deps, "self dependency")
    require(
        all(dep in ids for j in jobs for dep in j["dependencies"]), "unknown dependency"
    )
    by_id = {j["id"]: j for j in jobs}
    visited, visiting = set(), set()

    def dfs(node):
        require(node not in visiting, "dependency cycle")
        if node in visited:
            return
        visiting.add(node)
        for dep in by_id[node]["dependencies"]:
            dfs(dep)
        visiting.remove(node)
        visited.add(node)

    for node in ids:
        dfs(node)
    return plan, sha(raw)


def reconcile_running_job(worker_db: Path, task_id: str):
    if not worker_db.exists():
        return "RECONCILIATION_REQUIRED"
    with closing(sqlite3.connect(f"file:{worker_db}?mode=ro", uri=True)) as db:
        found = db.execute("SELECT state FROM work WHERE id=?", (task_id,)).fetchone()
        if found and found[0] == "DONE":
            return "DONE_CANDIDATE"
    return "RECONCILIATION_REQUIRED"


def cycle(db, plan, plan_path: Path, worker: Path):
    rows = {r[0]: r[1] for r in db.execute("SELECT id,state FROM jobs")}
    completed, blocked = [], []
    for job in plan["jobs"]:
        jid = job["id"]
        state = rows.get(jid, "OPEN")
        if state == "DONE":
            completed.append(jid)
            continue
        if state in ("RECONCILIATION_REQUIRED", "INTEGRITY_FAILURE"):
            blocked.append(jid)
            continue
        if state == "RUNNING":
            prior_state = reconcile_running_job(ROOT / "writer-ledger.sqlite3", jid)
            if prior_state == "DONE_CANDIDATE":
                task_path = plan_path.parent / job["task_file"]
                require(
                    sha(task_path.read_bytes()) == job["task_sha256"],
                    "INTEGRITY_FAILURE task modified during recovery",
                )
                require(
                    sha(worker.read_bytes()) == plan["worker_sha256"],
                    "INTEGRITY_FAILURE worker modified during recovery",
                )
                verified = subprocess.run(
                    [sys.executable, str(worker), "--task", str(task_path)],
                    capture_output=True,
                    text=True,
                    timeout=80,
                )
                try:
                    payload = json.loads(verified.stdout.strip().splitlines()[-1])
                except (IndexError, json.JSONDecodeError):
                    payload = {}
                if verified.returncode == 0 and payload.get("state") == "DONE":
                    note(
                        db,
                        jid,
                        "DONE",
                        {"recovered": True, "remote_reconciled": payload},
                    )
                    rows[jid] = "DONE"
                    completed.append(jid)
                    continue
            note(
                db,
                jid,
                "RECONCILIATION_REQUIRED",
                {"worker_state": prior_state, "no_mutation_retry": True},
            )
            blocked.append(jid)
            continue
        if any(rows.get(dep) != "DONE" for dep in job["dependencies"]):
            blocked.append(jid)
            continue
        task_path = plan_path.parent / job["task_file"]
        require(
            sha(task_path.read_bytes()) == job["task_sha256"],
            "INTEGRITY_FAILURE task modified after preflight",
        )
        require(
            sha(worker.read_bytes()) == plan["worker_sha256"],
            "INTEGRITY_FAILURE worker modified after preflight",
        )
        note(
            db,
            jid,
            "RUNNING",
            {"worker_sha256": plan["worker_sha256"], "task_sha256": job["task_sha256"]},
        )
        result = subprocess.run(
            [sys.executable, str(worker), "--task", str(task_path)],
            capture_output=True,
            text=True,
            timeout=220,
        )
        if result.returncode == 0:
            try:
                payload = json.loads(result.stdout.strip().splitlines()[-1])
            except (IndexError, json.JSONDecodeError) as exc:
                note(
                    db,
                    jid,
                    "RECONCILIATION_REQUIRED",
                    {"error": f"unverified worker output {exc}"},
                )
                blocked.append(jid)
                continue
            if payload.get("state") == "DONE":
                note(db, jid, "DONE", {"worker_result": payload})
                completed.append(jid)
                rows[jid] = "DONE"
                continue
        writer_db = ROOT / "writer-ledger.sqlite3"
        reserved = False
        if writer_db.exists():
            with closing(
                sqlite3.connect(f"file:{writer_db}?mode=ro", uri=True)
            ) as writer_conn:
                reserved = (
                    writer_conn.execute(
                        "SELECT 1 FROM work WHERE id=?", (jid,)
                    ).fetchone()
                    is not None
                )
        if not reserved and "RESOURCE_EXHAUSTED" in result.stderr:
            note(
                db,
                jid,
                "RESOURCE_BLOCKED",
                {
                    "returncode": result.returncode,
                    "error": result.stderr[-300:],
                    "retry_only_after_resource_preflight": True,
                },
            )
        elif not reserved and "INTEGRITY_BLOCKED" in result.stderr:
            note(
                db,
                jid,
                "INTEGRITY_FAILURE",
                {
                    "returncode": result.returncode,
                    "error": result.stderr[-300:],
                    "new_head_reconciliation_required": True,
                },
            )
        else:
            note(
                db,
                jid,
                "RECONCILIATION_REQUIRED",
                {
                    "returncode": result.returncode,
                    "stdout": result.stdout[-500:],
                    "stderr": result.stderr[-300:],
                    "no_mutation_retry": True,
                },
            )
        blocked.append(jid)
    return completed, blocked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--worker", type=Path, required=True)
    ap.add_argument("--validate-only", action="store_true")
    args = ap.parse_args()
    plan, digest = load_plan(args.plan, args.worker)
    if args.validate_only:
        print(
            json.dumps(
                {
                    "state": "PLAN_VALID",
                    "epoch": plan["epoch_id"],
                    "jobs": len(plan["jobs"]),
                    "plan_sha256": digest,
                }
            )
        )
        return 0
    ROOT.mkdir(parents=True, exist_ok=True)
    with LOCK.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("SECOND_DISPATCHER_BLOCKED")
            return 2
        db = init()
        try:
            existing = db.execute(
                "SELECT plan_sha,status FROM epochs WHERE id=?", (plan["epoch_id"],)
            ).fetchone()
            if existing:
                require(existing[0] == digest, "INTEGRITY_FAILURE changed epoch plan")
                db.execute(
                    "UPDATE epochs SET heartbeat_utc=?,restarts=restarts+1 WHERE id=?",
                    (utc(), plan["epoch_id"]),
                )
            else:
                db.execute(
                    "INSERT INTO epochs(id,plan_sha,status,created_utc,heartbeat_utc) VALUES (?,?,?,?,?)",
                    (plan["epoch_id"], digest, "RUNNING", utc(), utc()),
                )
            for job in plan["jobs"]:
                row = db.execute(
                    "SELECT task_sha FROM jobs WHERE id=?", (job["id"],)
                ).fetchone()
                if row:
                    require(
                        row[0] == job["task_sha256"],
                        "INTEGRITY_FAILURE job redefinition",
                    )
                else:
                    db.execute(
                        "INSERT INTO jobs(id,state,task_sha,updated_utc) VALUES (?,?,?,?)",
                        (job["id"], "OPEN", job["task_sha256"], utc()),
                    )
            completed, blocked = cycle(db, plan, args.plan, args.worker)
            all_done = len(completed) == len(plan["jobs"])
            status = "COMPLETE" if all_done else "BLOCKED_OR_OPEN"
            db.execute(
                "UPDATE epochs SET status=?,heartbeat_utc=? WHERE id=?",
                (status, utc(), plan["epoch_id"]),
            )
            print(
                json.dumps(
                    {
                        "epoch": plan["epoch_id"],
                        "state": status,
                        "completed": completed,
                        "blocked": blocked,
                    },
                    sort_keys=True,
                )
            )
            return 0 if all_done else 3
        finally:
            db.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(
            json.dumps({"state": "FAIL_CLOSED", "error": str(exc)[:350]}),
            file=sys.stderr,
        )
        sys.exit(4)
