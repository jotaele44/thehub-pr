"""Fixture suite for fail-closed durable source writer (offline)."""

import base64
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/afk/ecpaf_repo_worker.py"
if not SOURCE.exists():
    SOURCE = ROOT / "afk_repo_worker.py"


def make_module():
    spec = importlib.util.spec_from_file_location("afk_repo_worker_fixture", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="afk-v22-writer-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.m = make_module()
        self.m.ROOT = self.base / "audit"
        self.m.ROOT.mkdir()
        self.m.STATE = self.m.ROOT / "state.sqlite3"
        self.m.WORK_ROOT = self.base / "worktrees"
        self.m.REPO_ROOT = self.base / "repos"
        self.m.REPO_ROOT.mkdir()
        self.m.MIN_FREE_BYTES = 0
        self.repo = "thehub-pr"
        self.local = self.m.REPO_ROOT / self.repo
        self.remote = self.base / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", str(self.remote)], check=True)
        subprocess.run(["git", "init", "-q", str(self.local)], check=True)
        (self.local / "README.md").write_text("fixture\n")
        subprocess.run(["git", "-C", str(self.local), "add", "README.md"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.local),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-q",
                "-m",
                "base",
            ],
            check=True,
        )
        self.sha = subprocess.check_output(
            ["git", "-C", str(self.local), "rev-parse", "HEAD"], text=True
        ).strip()
        subprocess.run(
            ["git", "-C", str(self.local), "branch", "-M", "main"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.local), "remote", "add", "origin", str(self.remote)],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.local), "push", "-q", "-u", "origin", "main"],
            check=True,
        )
        self.created = []
        self.actual_command = self.m.command
        self.m.command = self.command
        self.m.github = self.github
        self.m.remote_branch = self.remote_branch
        self.conn = self.m.connection()
        self.addCleanup(self.conn.close)
        self.task = self.task_for("A real repeatable queue runner fixture\n")

    def task_for(self, data):
        payload = data.encode()
        return {
            "schema": "ecpaf-v2.2-repo-task/1",
            "id": "afk-worker-fixture-20261111",
            "repository": self.repo,
            "base_sha": self.sha,
            "branch": "feat/ecpaf-v22-test-fixture-20261111",
            "title": "feat(afk): evidence-only workflow pilot",
            "description": "Predeclared deterministic pilot with no protected operations.",
            "authorization": "AI_AUTO",
            "mode": "DRAFT_PR_ONLY",
            "edits": [
                {
                    "path": "docs/afk/worker-proof.md",
                    "before_sha256": None,
                    "after_sha256": hashlib.sha256(payload).hexdigest(),
                    "content_b64": base64.b64encode(payload).decode(),
                }
            ],
        }

    def remote_branch(self, repo, branch):
        q = subprocess.run(
            [
                "git",
                "--git-dir",
                str(self.remote),
                "rev-parse",
                "--verify",
                "refs/heads/" + branch,
            ],
            capture_output=True,
            text=True,
        )
        return q.stdout.strip() if q.returncode == 0 else None

    def github(self, path):
        if path == "repos/jotaele44/thehub-pr/commits/main":
            return {"sha": self.sha}
        if path.startswith("repos/jotaele44/thehub-pr/pulls?"):
            return (
                [
                    {
                        "head": {
                            "ref": self.task["branch"],
                            "repo": {"name": self.repo},
                            "sha": self.remote_branch(self.repo, self.task["branch"]),
                        },
                        "draft": True,
                        "html_url": "https://github.com/jotaele44/thehub-pr/pull/999",
                    }
                ]
                if self.created
                else []
            )
        raise AssertionError("unexpected github request " + path)

    def command(self, args, cwd=None, timeout=55):
        if args[:3] == ["/usr/local/bin/gh", "pr", "create"]:
            self.created.append(args)
            return "https://github.com/jotaele44/thehub-pr/pull/999"
        return self.actual_command(args, cwd=cwd, timeout=timeout)

    def test_valid_task_schema(self):
        self.assertEqual(self.m.validate(self.task), ["docs/afk/worker-proof.md"])

    def test_traversal_and_git_path_rejected(self):
        for path in (
            "docs/../secrets.txt",
            ".git/config",
            "scripts/.git/foo.py",
            "/tmp/evil.py",
            "../out.py",
            "docs/secret.sh",
        ):
            self.task["edits"][0]["path"] = path
            with self.assertRaises(RuntimeError, msg=path):
                self.m.validate(self.task)

    def test_declared_payload_mismatch_rejected(self):
        self.task["edits"][0]["after_sha256"] = "f" * 64
        with self.assertRaises(RuntimeError):
            self.m.validate(self.task)

    def test_authorization_and_mode_rejected(self):
        self.task["authorization"] = "UNAPPROVED"
        with self.assertRaises(RuntimeError):
            self.m.validate(self.task)
        self.task["authorization"] = "AI_AUTO"
        self.task["mode"] = "MERGE"
        with self.assertRaises(RuntimeError):
            self.m.validate(self.task)

    def test_branch_and_repo_allowlist_rejected(self):
        self.task["repository"] = "outside-repo"
        with self.assertRaises(RuntimeError):
            self.m.validate(self.task)
        self.task["repository"] = self.repo
        self.task["branch"] = "main"
        with self.assertRaises(RuntimeError):
            self.m.validate(self.task)

    def test_duplicate_paths_rejected(self):
        self.task["edits"].append(dict(self.task["edits"][0]))
        with self.assertRaises(RuntimeError):
            self.m.validate(self.task)

    def test_stale_main_blocks_without_operation(self):
        self.task["base_sha"] = "a" * 40
        with self.assertRaises(RuntimeError):
            self.m.execute(self.conn, self.task)
        self.assertEqual(
            self.conn.execute("select count(*) from work").fetchone()[0], 0
        )

    def test_dirty_primary_blocks_without_operation(self):
        (self.local / "README.md").write_text("dirty\n")
        with self.assertRaises(RuntimeError):
            self.m.execute(self.conn, self.task)
        self.assertEqual(
            self.conn.execute("select count(*) from work").fetchone()[0], 0
        )

    def test_frozen_task_draft_pr_replay_idempotent(self):
        result = self.m.execute(self.conn, self.task)
        self.assertEqual(result["state"], "DONE")
        self.assertEqual(len(self.created), 1)
        pushed = self.remote_branch(self.repo, self.task["branch"])
        self.assertEqual(result["commit"], pushed)
        again = self.m.execute(self.conn, self.task)
        self.assertEqual(again["state"], "DONE")
        self.assertEqual(len(self.created), 1)
        self.assertEqual(
            self.conn.execute("select count(*) from work").fetchone()[0], 1
        )
        self.assertEqual(
            self.conn.execute("select state from work").fetchone()[0], "DONE"
        )
        self.assertFalse((self.m.WORK_ROOT / ("afk-v22-" + self.task["id"])).exists())

    def test_prepared_reconciliation_requires_review(self):
        self.conn.execute(
            "INSERT INTO work(id,state,baseline,branch,started,updated) VALUES (?,?,?,?,?,?)",
            (self.task["id"], "PREPARED", self.sha, self.task["branch"], "now", "now"),
        )
        result = self.m.execute(self.conn, self.task)
        self.assertEqual(result["state"], "RECONCILIATION_REQUIRED")
        self.assertEqual(len(self.created), 0)


if __name__ == "__main__":
    unittest.main()
