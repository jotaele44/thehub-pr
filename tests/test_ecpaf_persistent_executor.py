"""Offline adversarial tests for persistent ECPAF execution admission."""

from __future__ import annotations

import datetime as dt
from contextlib import closing
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/afk/ecpaf_persistent_executor.py"
if not SOURCE.is_file():
    SOURCE = ROOT / "ecpaf_persistent_executor.py"


def module():
    spec = importlib.util.spec_from_file_location("ecpaf_persistent", SOURCE)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


class PersistentExecutorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ecpaf-persistent-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.files = self.root / "sources"
        self.files.mkdir()
        self.state = self.root / "state"
        self.state.mkdir()
        self.m = module()
        self.now = dt.datetime.now(dt.timezone.utc)
        self.worker = self.files / "worker.py"
        self.worker.write_text("pass\n")
        self.dispatch = self.files / "dispatch.py"
        self.plan = self.files / "plan.json"
        self.task = self.files / "fixture-bounded-job-20261111.json"
        self.task.write_text(
            json.dumps(
                {
                    "id": "fixture-bounded-job-20261111",
                    "mode": "DRAFT_PR_ONLY",
                    "authorization": "AI_AUTO",
                }
            )
        )
        self.dispatch.write_text(
            "import json\nprint(json.dumps({'epoch':'afk-v22-fixture-20261111','state':'COMPLETE'}))\n"
        )
        self.plan.write_text(
            json.dumps(
                {
                    "schema": "ecpaf-v2.2-dispatch/1",
                    "epoch_id": "afk-v22-fixture-20261111",
                    "worker_sha256": self.sha(self.worker),
                    "jobs": [
                        {
                            "id": "fixture-bounded-job-20261111",
                            "task_file": self.task.name,
                            "task_sha256": self.sha(self.task),
                            "dependencies": [],
                        }
                    ],
                }
            )
        )
        self.config = {
            "schema": "ecpaf-v2.2-persistent-execution/1",
            "epoch_id": "afk-v22-fixture-20261111",
            "created_utc": self.now.isoformat(),
            "expires_utc": (self.now + dt.timedelta(hours=3)).isoformat(),
            "interval_seconds": 120,
            "plan_file": self.plan.name,
            "plan_sha256": self.sha(self.plan),
            "dispatcher_file": self.dispatch.name,
            "dispatcher_sha256": self.sha(self.dispatch),
            "worker_file": self.worker.name,
            "worker_sha256": self.sha(self.worker),
            "authorized_modes": ["DRAFT_PR_ONLY"],
            "protected_operations": [],
            "max_jobs": 1,
            "minimum_free_bytes": 2 * 1024**3,
            "certification": "WITHHELD",
        }
        self.admission = self.files / "admission.json"
        self.write()

    @staticmethod
    def sha(file):
        return hashlib.sha256(file.read_bytes()).hexdigest()

    def write(self):
        self.admission.write_text(json.dumps(self.config, sort_keys=True))

    def test_admission(self):
        a, state = self.m.load_admission(self.admission, now=self.now)
        self.assertEqual(state, "READY")
        self.assertEqual(a["protected_operations"], [])

    def test_completed_dispatch_replays_without_worker_side_effects(self):
        first = self.m.tick(self.admission, self.state, now=self.now)
        second = self.m.tick(self.admission, self.state, now=self.now)
        self.assertEqual([first["state"], second["state"]], ["PASS", "PASS"])
        with closing(sqlite3.connect(self.state / "execution.sqlite3")) as db:
            ticks = db.execute("SELECT state,receipt_sha256 FROM ticks").fetchall()
            self.assertEqual(len(ticks), 2)
            self.assertEqual(len(list(db.execute("SELECT * FROM admission"))), 1)
        for _, evidence in ticks:
            self.assertEqual(
                self.sha(self.state / "receipts" / f"{evidence}.json"), evidence
            )

    def test_expiration_one_receipt_only(self):
        late = self.now + dt.timedelta(hours=3, seconds=1)
        self.assertEqual(
            self.m.tick(self.admission, self.state, now=late)["state"], "EXPIRED"
        )
        self.assertEqual(
            self.m.tick(self.admission, self.state, now=late)["state"],
            "ALREADY_EXPIRED",
        )
        with closing(sqlite3.connect(self.state / "execution.sqlite3")) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM ticks").fetchone()[0], 1)

    def test_policy_authorization_rejected(self):
        self.config["protected_operations"] = ["MERGE"]
        self.write()
        with self.assertRaisesRegex(RuntimeError, "AUTHORIZATION_BLOCKED"):
            self.m.load_admission(self.admission)

    def test_worker_tampering_rejected(self):
        self.worker.write_text("bad\n")
        with self.assertRaisesRegex(RuntimeError, "byte mutation"):
            self.m.load_admission(self.admission)

    def test_plan_task_tampering_rejected(self):
        self.task.write_text("changed")
        with self.assertRaisesRegex(RuntimeError, "byte mutation"):
            self.m.load_admission(self.admission)

    def test_admission_alteration_on_restart_rejected(self):
        self.assertEqual(self.m.tick(self.admission, self.state)["state"], "PASS")
        self.config["max_jobs"] = 2
        self.write()
        with self.assertRaisesRegex(RuntimeError, "admission changed"):
            self.m.tick(self.admission, self.state)

    def test_historical_receipt_corruption_rejected(self):
        evidence = self.m.tick(self.admission, self.state)
        (self.state / "receipts" / (evidence["receipt"] + ".json")).write_text(
            "corrupt"
        )
        with self.assertRaisesRegex(RuntimeError, "receipt hash"):
            self.m.tick(self.admission, self.state)

    def test_missing_referenced_receipt_rejected(self):
        evidence = self.m.tick(self.admission, self.state)
        (self.state / "receipts" / (evidence["receipt"] + ".json")).unlink()
        with self.assertRaisesRegex(RuntimeError, "missing receipt"):
            self.m.tick(self.admission, self.state)

    def test_singleton_lock_blocks_second_worker(self):
        lock = self.state / "singleton.lock"
        with lock.open("a+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(
                self.m.tick(self.admission, self.state)["state"], "SINGLETON_BLOCKED"
            )
        self.assertFalse((self.state / "execution.sqlite3").exists())

    def test_storage_pressure_blocks_dispatch(self):
        with patch.object(self.m.os, "statvfs") as fake:
            fake.return_value.f_bavail = 0
            fake.return_value.f_frsize = 1
            self.assertEqual(
                self.m.tick(self.admission, self.state)["state"], "RESOURCE_BLOCKED"
            )
        with closing(sqlite3.connect(self.state / "execution.sqlite3")) as db:
            self.assertEqual(
                db.execute("SELECT state FROM ticks").fetchone()[0], "RESOURCE_BLOCKED"
            )

    def test_running_failed_dispatch_stays_reconciliation_required(self):
        self.dispatch.write_text("import sys\nsys.exit(12)\n")
        self.config["dispatcher_sha256"] = self.sha(self.dispatch)
        self.write()
        self.assertEqual(
            self.m.tick(self.admission, self.state)["state"], "RECONCILIATION_REQUIRED"
        )

    def test_expiry_cannot_enable_protected_task(self):
        self.config["authorized_modes"] = ["DRAFT_PR_ONLY", "MERGE"]
        self.write()
        with self.assertRaisesRegex(RuntimeError, "AUTHORIZATION_BLOCKED"):
            self.m.load_admission(self.admission)

    def test_admission_max_jobs_bound(self):
        self.config["max_jobs"] = 13
        self.write()
        with self.assertRaisesRegex(RuntimeError, "max jobs"):
            self.m.load_admission(self.admission)

    def test_unexpected_task_mode_fails_closed(self):
        self.task.write_text(
            json.dumps(
                {
                    "id": "fixture-bounded-job-20261111",
                    "mode": "MERGE",
                    "authorization": "AI_AUTO",
                }
            )
        )
        self.config["plan_sha256"] = self.sha(self.plan)
        data = json.loads(self.plan.read_text())
        data["jobs"][0]["task_sha256"] = self.sha(self.task)
        self.plan.write_text(json.dumps(data))
        self.config["plan_sha256"] = self.sha(self.plan)
        self.write()
        with self.assertRaisesRegex(RuntimeError, "AUTHORIZATION_BLOCKED"):
            self.m.load_admission(self.admission)


if __name__ == "__main__":
    unittest.main()
