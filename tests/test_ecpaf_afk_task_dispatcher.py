"""Isolated AFK task DAG, recovery and duplicate-effect negative tests."""

import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/afk/ecpaf_task_dispatcher.py"
if not SOURCE.exists():
    SOURCE = ROOT / "afk_task_dispatcher.py"


def module():
    spec = importlib.util.spec_from_file_location("afk_dispatcher_fixture", SOURCE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class DispatcherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="afk-dispatch-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.m = module()
        self.m.ROOT = self.root
        self.m.DB = self.root / "ledger.sqlite3"
        self.m.LOCK = self.root / "lock"
        self.worker = self.root / "worker.py"
        self.worker.write_text("pass\n")
        self.plan_path = self.root / "plan.json"
        self.jobs = []
        self.db = self.m.init()
        self.addCleanup(lambda: self.db.close())

    def job(self, name, deps=None):
        manifest = self.root / (name + ".json")
        manifest.write_text(json.dumps({"id": name}))
        item = {
            "id": name,
            "task_file": manifest.name,
            "task_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            "dependencies": deps or [],
        }
        self.jobs.append(item)
        self.db.execute(
            "INSERT INTO jobs(id,state,task_sha,updated_utc) VALUES (?,?,?,?)",
            (name, "OPEN", item["task_sha256"], "now"),
        )
        return item

    def plan(self):
        p = {
            "schema": "ecpaf-v2.2-dispatch/1",
            "epoch_id": "afk-v22-fixture-20261111",
            "worker_sha256": hashlib.sha256(self.worker.read_bytes()).hexdigest(),
            "jobs": self.jobs,
        }
        self.plan_path.write_text(json.dumps(p))
        return p

    def test_valid_plan(self):
        self.job("fixture-source-one")
        p = self.plan()
        out, receipt = self.m.load_plan(self.plan_path, self.worker)
        self.assertEqual(out, p)
        self.assertEqual(
            receipt, hashlib.sha256(self.plan_path.read_bytes()).hexdigest()
        )

    def test_worker_or_manifest_drift_is_integrity_failure(self):
        self.job("fixture-source-one")
        self.plan()
        self.worker.write_text("mutated\n")
        with self.assertRaisesRegex(RuntimeError, "worker source mismatch"):
            self.m.load_plan(self.plan_path, self.worker)
        self.worker.write_text("pass\n")
        (self.root / "fixture-source-one.json").write_text('{"id":"mutated"}')
        with self.assertRaisesRegex(RuntimeError, "task manifest differs"):
            self.m.load_plan(self.plan_path, self.worker)

    def test_dependency_cycle_rejected(self):
        self.job("fixture-source-one", ["fixture-source-two"])
        self.job("fixture-source-two", ["fixture-source-one"])
        self.plan()
        with self.assertRaisesRegex(RuntimeError, "dependency cycle"):
            self.m.load_plan(self.plan_path, self.worker)

    def test_unknown_dependency_rejected(self):
        self.job("fixture-source-one", ["not-in-graph"])
        self.plan()
        with self.assertRaisesRegex(RuntimeError, "unknown dependency"):
            self.m.load_plan(self.plan_path, self.worker)

    def test_ready_work_is_ordered_and_once_only(self):
        self.job("fixture-source-one")
        self.job("fixture-source-two", ["fixture-source-one"])
        p = self.plan()
        calls = []

        def execute(args, **kwargs):
            calls.append(args[-1])
            return subprocess.CompletedProcess(
                args,
                0,
                stdout=json.dumps({"state": "DONE", "receipt": "fixture"}) + "\n",
                stderr="",
            )

        with patch.object(self.m.subprocess, "run", side_effect=execute):
            done, blocked = self.m.cycle(self.db, p, self.plan_path, self.worker)
            self.assertEqual(done, ["fixture-source-one", "fixture-source-two"])
            self.assertEqual(blocked, [])
            done_again, _ = self.m.cycle(self.db, p, self.plan_path, self.worker)
            self.assertEqual(len(done_again), 2)
        self.assertEqual(len(calls), 2)
        self.assertEqual(
            self.db.execute("select count(*) from jobs where state='DONE'").fetchone()[
                0
            ],
            2,
        )

    def test_running_without_receipt_never_reissues_mutation(self):
        self.job("fixture-source-one")
        p = self.plan()
        self.db.execute("UPDATE jobs SET state='RUNNING'")
        with patch.object(
            self.m.subprocess, "run", side_effect=AssertionError("should not run")
        ):
            _, blocked = self.m.cycle(self.db, p, self.plan_path, self.worker)
        self.assertEqual(blocked, ["fixture-source-one"])
        self.assertEqual(
            self.db.execute("select state from jobs").fetchone()[0],
            "RECONCILIATION_REQUIRED",
        )

    def test_running_done_candidate_remote_reconciled(self):
        self.job("fixture-source-one")
        p = self.plan()
        self.db.execute("UPDATE jobs SET state='RUNNING'")
        workerdb = sqlite3.connect(self.root / "writer-ledger.sqlite3")
        workerdb.execute("CREATE TABLE work(id TEXT, state TEXT)")
        workerdb.execute(
            "INSERT INTO work VALUES (?,?)", ("fixture-source-one", "DONE")
        )
        workerdb.commit()
        workerdb.close()
        calls = []

        def fake(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(
                args,
                0,
                stdout='{"state":"DONE","pull_request":"https://example.invalid"}',
                stderr="",
            )

        with patch.object(self.m.subprocess, "run", side_effect=fake):
            done, blocked = self.m.cycle(self.db, p, self.plan_path, self.worker)
        self.assertEqual(done, ["fixture-source-one"])
        self.assertEqual(blocked, [])
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            self.db.execute("select state from jobs").fetchone()[0], "DONE"
        )

    def test_resource_blocked_can_retry_when_no_worker_side_effect(self):
        self.job("fixture-source-one")
        p = self.plan()
        calls = []

        def exhausted(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(
                args, 4, stdout="", stderr="RESOURCE_EXHAUSTED free space"
            )

        with patch.object(self.m.subprocess, "run", side_effect=exhausted):
            _, blocked = self.m.cycle(self.db, p, self.plan_path, self.worker)
        self.assertEqual(blocked, ["fixture-source-one"])
        self.assertEqual(
            self.db.execute("select state from jobs").fetchone()[0], "RESOURCE_BLOCKED"
        )

        def repaired(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(
                args, 0, stdout='{"state":"DONE"}', stderr=""
            )

        with patch.object(self.m.subprocess, "run", side_effect=repaired):
            done, _ = self.m.cycle(self.db, p, self.plan_path, self.worker)
        self.assertEqual(done, ["fixture-source-one"])
        self.assertEqual(len(calls), 2)

    def test_integrity_failure_not_retried(self):
        self.job("fixture-source-one")
        p = self.plan()

        def fail(args, **kwargs):
            return subprocess.CompletedProcess(
                args, 4, stdout="", stderr="INTEGRITY_BLOCKED main changed"
            )

        with patch.object(self.m.subprocess, "run", side_effect=fail):
            _, blocked = self.m.cycle(self.db, p, self.plan_path, self.worker)
        self.assertEqual(blocked, ["fixture-source-one"])
        self.assertEqual(
            self.db.execute("select state from jobs").fetchone()[0], "INTEGRITY_FAILURE"
        )

    def test_receipts_are_content_addressed(self):
        receipt = self.m.receipt({"message": "fixture"})
        self.assertEqual(self.m.receipt({"message": "fixture"}), receipt)
        p = self.root / "dispatch_receipts" / f"{receipt}.json"
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), receipt)
        p.write_text("tampered")
        with self.assertRaisesRegex(RuntimeError, "INTEGRITY_FAILURE"):
            self.m.receipt({"message": "fixture"})


if __name__ == "__main__":
    unittest.main()
