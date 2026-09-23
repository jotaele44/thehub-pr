from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "federation_completion_runner",
    ROOT / "scripts" / "federation_completion_runner.py",
)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


def test_parse_remote_gate_groups_states_by_repo(tmp_path):
    ledger = tmp_path / "remote.json"
    ledger.write_text(
        json.dumps(
            {
                "certification": "FAIL_ACTIONABLE_RESIDUE",
                "open_pr_denominator": 3,
                "counts": {"BLOCKED": 2, "REBASE_REQUIRED": 1},
                "actionable_counts": {"REBASE_REQUIRED": 1},
                "open_pr_denominator_complete": True,
                "audit_truncated": False,
                "errors": [],
                "rows": [
                    {"repository": "owner/a", "state": "BLOCKED"},
                    {"repository": "owner/a", "state": "REBASE_REQUIRED"},
                    {"repository": "owner/b", "state": "BLOCKED"},
                ],
            }
        )
    )

    parsed = runner.parse_remote_gate(ledger)

    assert parsed["open_pr_denominator"] == 3
    assert parsed["by_repo"] == {
        "owner/a": {"BLOCKED": 1, "REBASE_REQUIRED": 1},
        "owner/b": {"BLOCKED": 1},
    }


def test_parse_startup_audit_keeps_product_completion_separate(tmp_path):
    ledger = tmp_path / "startup.json"
    ledger.write_text(
        json.dumps(
            {
                "startup_setup_certification": "PASS",
                "product_completion_certification": "PROVISIONAL",
                "arithmetic": {"closed": True},
                "product_arithmetic": {"closed": True},
                "code_completion_arithmetic": {
                    "closed": True,
                    "counts": {"CODE_COMPLETE_CANDIDATE": 1},
                },
                "repositories": [
                    {
                        "repo_id": "moneysweep-pr",
                        "code_completion_state": "CODE_COMPLETE_CANDIDATE",
                        "startup_setup_state": "STARTUP_SETUP_COMPLETE",
                        "product_completion_state": "BLOCKED_FOR_PRODUCT_COMPLETION",
                        "production_status": "NON_PRODUCTION_DIAGNOSTIC",
                        "ready_for_hub_live_execution": False,
                        "code_completion_blockers": [],
                        "startup_setup_blockers": [],
                        "product_completion_blockers": ["MANIFEST_READY_FOR_HUB_LIVE_EXECUTION_FALSE"],
                    }
                ],
            }
        )
    )

    parsed = runner.parse_startup_audit(ledger)

    assert parsed["startup_setup_certification"] == "PASS"
    assert parsed["product_completion_certification"] == "PROVISIONAL"
    assert parsed["code_completion_arithmetic"]["counts"] == {"CODE_COMPLETE_CANDIDATE": 1}
    assert parsed["repositories"][0]["code_completion_state"] == "CODE_COMPLETE_CANDIDATE"
    assert parsed["repositories"][0]["startup_setup_state"] == "STARTUP_SETUP_COMPLETE"
    assert parsed["repositories"][0]["product_completion_blockers"] == [
        "MANIFEST_READY_FOR_HUB_LIVE_EXECUTION_FALSE"
    ]


def test_sha256_file_hashes_bytes(tmp_path):
    payload = tmp_path / "payload.txt"
    payload.write_text("federation\n")

    assert runner.sha256_file(payload) == (
        "b80eaae6f33a4751e54db4ab30861caa79a5de5a8c6ea3df7412920ee40ab0a6"
    )


def test_python_alias_env_adds_python_when_missing(monkeypatch):
    def fake_run_capture(args, cwd, *, env=None):
        class Result:
            returncode = 1
            stdout = ""
            stderr = ""

        return Result()

    monkeypatch.setattr(runner, "run_capture", fake_run_capture)
    env, shim_dir = runner.python_alias_env()

    assert shim_dir is not None
    assert env["PATH"].startswith(shim_dir)
    assert (Path(shim_dir) / "python").exists()


def test_write_implementation_plan_keeps_code_completion_candidate_bounded(tmp_path):
    plan = tmp_path / "IMPLEMENTATION_PLAN.md"
    runner.write_implementation_plan(
        plan,
        {
            "generated_utc": "2026-09-05T00:00:00Z",
            "run_id": "run",
            "certification": "AUDIT_ONLY",
            "remote_gate": {
                "open_pr_denominator": 1,
                "certification": "FAIL_ACTIONABLE_RESIDUE",
                "counts": {"BLOCKED": 1},
                "actionable_counts": {},
            },
            "startup_audit": {
                "startup_setup_certification": "PROVISIONAL",
                "product_completion_certification": "PROVISIONAL",
                "code_completion_arithmetic": {"counts": {"CODE_COMPLETE_CANDIDATE": 1}},
                "arithmetic": {"counts": {"BLOCKED": 1}},
                "product_arithmetic": {"counts": {"BLOCKED_FOR_PRODUCT_COMPLETION": 1}},
                "repositories": [
                    {
                        "repo_id": "thehub-pr",
                        "code_completion_state": "CODE_COMPLETE_CANDIDATE",
                        "code_completion_blockers": [],
                        "product_completion_blockers": ["startup_setup_state:BLOCKED"],
                    }
                ],
            },
        },
    )

    text = plan.read_text()
    assert "CODE_COMPLETE_CANDIDATE is not source-certified or product-certified" in text
    assert "CERTIFIED` is not emitted by this runner" in text
