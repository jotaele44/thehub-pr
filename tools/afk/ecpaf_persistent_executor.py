#!/usr/bin/env python3
"""ECPAF-V2.2 persistent execution adapter, safe to invoke through launchd.

An immutable scoped admission binds a byte-pinned dispatcher and worker to a
frozen task graph for a finite duration. The adapter itself never merges PRs,
changes branch protection, or creates/adapts task plans.
"""

from __future__ import annotations

import argparse
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

MIN_FREE_BYTES = 2 * 1024**3
MAX_WINDOW_SECONDS = 4 * 3600
MIN_WINDOW_SECONDS = 180 * 60
MAX_HEARTBEAT_SECONDS = 300


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def canonical(obj: dict) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def verified_file(path: Path, expected: str, parent: Path) -> None:
    require(
        isinstance(expected, str)
        and re.fullmatch(r"[0-9a-f]{64}", expected) is not None,
        "INTEGRITY_FAILURE expected SHA-256 invalid",
    )
    require(
        path.is_file()
        and not path.is_symlink()
        and path.parent.resolve() == parent.resolve(),
        "INTEGRITY_FAILURE file location",
    )
    require(digest(path.read_bytes()) == expected, "INTEGRITY_FAILURE byte mutation")


def load_admission(path: Path, now: dt.datetime | None = None) -> tuple[dict, str]:
    now = now or dt.datetime.now(dt.timezone.utc)
    require(
        path.is_file() and not path.is_symlink(), "INTEGRITY_FAILURE admission path"
    )
    raw = path.read_bytes()
    # A restricted schema prevents excess capabilities in an apparently valid plan.
    a = json.loads(raw)
    fields = {
        "schema",
        "epoch_id",
        "created_utc",
        "expires_utc",
        "interval_seconds",
        "plan_file",
        "plan_sha256",
        "dispatcher_file",
        "dispatcher_sha256",
        "worker_file",
        "worker_sha256",
        "authorized_modes",
        "protected_operations",
        "max_jobs",
        "minimum_free_bytes",
        "certification",
    }
    require(set(a) == fields, "INTEGRITY_FAILURE admission schema")
    require(
        a["schema"] == "ecpaf-v2.2-persistent-execution/1",
        "INTEGRITY_FAILURE admission version",
    )
    require(
        isinstance(a["epoch_id"], str)
        and re.fullmatch(r"afk-v22-[a-z0-9-]{8,64}", a["epoch_id"]) is not None,
        "INTEGRITY_FAILURE epoch identity",
    )
    require(
        a["authorized_modes"] == ["DRAFT_PR_ONLY"]
        and a["protected_operations"] == []
        and a["certification"] == "WITHHELD",
        "AUTHORIZATION_BLOCKED protected operations",
    )
    require(
        type(a["interval_seconds"]) is int
        and 30 <= a["interval_seconds"] <= MAX_HEARTBEAT_SECONDS,
        "INTEGRITY_FAILURE interval",
    )
    require(
        type(a["max_jobs"]) is int and 1 <= a["max_jobs"] <= 12,
        "INTEGRITY_FAILURE max jobs",
    )
    require(
        type(a["minimum_free_bytes"]) is int
        and a["minimum_free_bytes"] >= MIN_FREE_BYTES,
        "INTEGRITY_FAILURE storage reserve",
    )
    start = dt.datetime.fromisoformat(a["created_utc"])
    expiry = dt.datetime.fromisoformat(a["expires_utc"])
    require(
        start.tzinfo is not None and expiry.tzinfo is not None,
        "INTEGRITY_FAILURE timezone",
    )
    require(
        MIN_WINDOW_SECONDS <= (expiry - start).total_seconds() <= MAX_WINDOW_SECONDS,
        "INTEGRITY_FAILURE execution window",
    )
    require(now >= start - dt.timedelta(minutes=2), "INTEGRITY_FAILURE clock offset")
    if now >= expiry:
        return a, "EXPIRED"
    parent = path.parent.resolve()
    for label in ("plan", "dispatcher", "worker"):
        name = a[label + "_file"]
        require(
            isinstance(name, str)
            and re.fullmatch(r"[a-zA-Z0-9_.-]{1,100}", name) is not None
            and name not in (".", ".."),
            "INTEGRITY_FAILURE filename",
        )
        verified_file(parent / name, a[label + "_sha256"], parent)
    plan = json.loads((parent / a["plan_file"]).read_bytes())
    require(
        plan.get("schema") == "ecpaf-v2.2-dispatch/1"
        and plan.get("epoch_id") == a["epoch_id"],
        "INTEGRITY_FAILURE plan identity",
    )
    require(
        isinstance(plan.get("jobs"), list) and 1 <= len(plan["jobs"]) <= a["max_jobs"],
        "INTEGRITY_FAILURE job denominator",
    )
    require(
        plan.get("worker_sha256") == a["worker_sha256"],
        "INTEGRITY_FAILURE worker identity",
    )
    for job in plan["jobs"]:
        require(
            isinstance(job, dict)
            and set(job) == {"id", "task_file", "task_sha256", "dependencies"},
            "INTEGRITY_FAILURE task shape",
        )
        task_name = job["task_file"]
        require(
            isinstance(task_name, str)
            and re.fullmatch(r"[a-z0-9][a-z0-9-]{6,58}\.json", task_name) is not None,
            "INTEGRITY_FAILURE task filename",
        )
        verified_file(parent / task_name, job["task_sha256"], parent)
        task = json.loads((parent / task_name).read_bytes())
        require(
            task.get("id") == job["id"]
            and task.get("mode") == "DRAFT_PR_ONLY"
            and task.get("authorization") == "AI_AUTO",
            "AUTHORIZATION_BLOCKED task scope",
        )
    return a, "READY"


def dbopen(root: Path) -> sqlite3.Connection:
    db = sqlite3.connect(root / "execution.sqlite3", timeout=20, isolation_level=None)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.execute(
        "CREATE TABLE IF NOT EXISTS admission (epoch TEXT PRIMARY KEY, sha256 TEXT NOT NULL, created_utc TEXT NOT NULL, state TEXT NOT NULL)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS ticks (id INTEGER PRIMARY KEY AUTOINCREMENT, epoch TEXT NOT NULL, at TEXT NOT NULL, state TEXT NOT NULL, detail TEXT NOT NULL, receipt_sha256 TEXT NOT NULL)"
    )
    return db


def verify_ledger(db: sqlite3.Connection, root: Path) -> dict:
    require(
        db.execute("PRAGMA quick_check").fetchone()[0] == "ok",
        "INTEGRITY_FAILURE SQLite integrity",
    )
    receipts = root / "receipts"
    found = set()
    if receipts.exists():
        require(
            receipts.is_dir() and not receipts.is_symlink(),
            "INTEGRITY_FAILURE receipts directory",
        )
        for path in receipts.iterdir():
            if path.suffix != ".json":
                continue
            require(
                path.is_file()
                and not path.is_symlink()
                and re.fullmatch(r"[0-9a-f]{64}", path.stem) is not None,
                "INTEGRITY_FAILURE receipt filename",
            )
            require(
                digest(path.read_bytes()) == path.stem, "INTEGRITY_FAILURE receipt hash"
            )
            found.add(path.stem)
    refs = {row[0] for row in db.execute("SELECT receipt_sha256 FROM ticks")}
    require(refs <= found, "INTEGRITY_FAILURE missing receipt")
    return {"receipts": len(found), "references": len(refs)}


def receipt(
    db: sqlite3.Connection, root: Path, epoch: str, state: str, detail: dict
) -> str:
    obj = {"at": utc(), "epoch": epoch, "state": state, "detail": detail}
    data = canonical(obj)
    value = digest(data)
    folder = root / "receipts"
    folder.mkdir(exist_ok=True)
    target = folder / f"{value}.json"
    if not target.exists():
        tmp = folder / f".{value}.{os.getpid()}.tmp"
        with tmp.open("xb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    require(digest(target.read_bytes()) == value, "INTEGRITY_FAILURE receipt write")
    db.execute(
        "INSERT INTO ticks(epoch,at,state,detail,receipt_sha256) VALUES(?,?,?,?,?)",
        (epoch, obj["at"], state, json.dumps(detail, sort_keys=True), value),
    )
    return value


def reconcile(db: sqlite3.Connection, root: Path, a: dict, admission_sha: str) -> None:
    previous = db.execute(
        "SELECT sha256 FROM admission WHERE epoch=?", (a["epoch_id"],)
    ).fetchone()
    if previous:
        require(
            previous[0] == admission_sha,
            "INTEGRITY_FAILURE admission changed across restarts",
        )
    else:
        db.execute(
            "INSERT INTO admission(epoch,sha256,created_utc,state) VALUES(?,?,?,?)",
            (a["epoch_id"], admission_sha, utc(), "ACTIVE"),
        )


def tick(admission: Path, root: Path, now: dt.datetime | None = None) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    with (root / "singleton.lock").open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"state": "SINGLETON_BLOCKED"}
        db = dbopen(root)
        try:
            evidence = verify_ledger(db, root)
            a, mode = load_admission(admission, now=now)
            reconcile(db, root, a, digest(admission.read_bytes()))
            if mode == "EXPIRED":
                prior = db.execute(
                    "SELECT COUNT(*) FROM ticks WHERE epoch=? AND state='EXPIRED'",
                    (a["epoch_id"],),
                ).fetchone()[0]
                if prior:
                    return {"state": "ALREADY_EXPIRED", "epoch": a["epoch_id"]}
                rec = receipt(db, root, a["epoch_id"], "EXPIRED", evidence)
                db.execute(
                    "UPDATE admission SET state='EXPIRED' WHERE epoch=?",
                    (a["epoch_id"],),
                )
                return {"state": "EXPIRED", "receipt": rec}
            free_bytes = os.statvfs(root).f_bavail * os.statvfs(root).f_frsize
            if free_bytes < a["minimum_free_bytes"]:
                rec = receipt(
                    db,
                    root,
                    a["epoch_id"],
                    "RESOURCE_BLOCKED",
                    {**evidence, "disk_free_bytes": free_bytes},
                )
                return {"state": "RESOURCE_BLOCKED", "receipt": rec}
            call = [
                sys.executable,
                str(admission.parent / a["dispatcher_file"]),
                "--plan",
                str(admission.parent / a["plan_file"]),
                "--worker",
                str(admission.parent / a["worker_file"]),
            ]
            try:
                result = subprocess.run(
                    call, text=True, capture_output=True, timeout=270
                )
                ok = False
                if result.returncode == 0:
                    try:
                        response = json.loads(result.stdout.strip().splitlines()[-1])
                        ok = (
                            response.get("epoch") == a["epoch_id"]
                            and response.get("state") == "COMPLETE"
                        )
                    except (IndexError, json.JSONDecodeError):
                        pass
                state = "PASS" if ok else "RECONCILIATION_REQUIRED"
                detail = {
                    "exit_code": result.returncode,
                    "stdout_tail": result.stdout[-500:],
                    "stderr_tail": result.stderr[-250:],
                    **evidence,
                }
            except subprocess.TimeoutExpired as exc:
                state = "RECONCILIATION_REQUIRED"
                detail = {"error": str(exc)[:250], **evidence}
            rec = receipt(db, root, a["epoch_id"], state, detail)
            return {"state": state, "receipt": rec}
        finally:
            db.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admission", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        outcome = tick(args.admission, args.state_dir)
    except Exception as exc:
        print(
            json.dumps({"state": "FAIL_CLOSED", "error": str(exc)[:300]}),
            file=sys.stderr,
        )
        return 3
    print(json.dumps(outcome, sort_keys=True))
    return (
        0
        if outcome["state"]
        in (
            "PASS",
            "EXPIRED",
            "ALREADY_EXPIRED",
            "SINGLETON_BLOCKED",
            "RESOURCE_BLOCKED",
        )
        else 4
    )


if __name__ == "__main__":
    raise SystemExit(main())
