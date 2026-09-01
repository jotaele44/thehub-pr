from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "startup_completion_audit",
    ROOT / "scripts" / "startup_completion_audit.py",
)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)


def _result(name: str, state: str = "PASS", reason: str | None = None):
    return audit.CommandResult(
        name=name,
        command=f"run {name}",
        state=state,
        exit_code=0 if state == "PASS" else 1,
        elapsed_seconds=0.1,
        log_path=None,
        reason=reason,
    )


def test_live_readiness_false_blocks_product_not_startup_setup():
    startup_state, startup_blockers, product_state, product_blockers = audit.classify_repo(
        "skywatcher-pr",
        False,
        [],
        [_result("setup"), _result("test_suite"), _result("export_canonical"), _result("startup_smoke")],
    )
    assert startup_state == "STARTUP_SETUP_COMPLETE"
    assert startup_blockers == []
    assert product_state == "BLOCKED_FOR_PRODUCT_COMPLETION"
    assert "MANIFEST_READY_FOR_HUB_LIVE_EXECUTION_FALSE" in product_blockers


def test_command_failure_fails_startup_setup_before_product_completion():
    startup_state, startup_blockers, product_state, product_blockers = audit.classify_repo(
        "moneysweep-pr",
        False,
        ["manual sources missing"],
        [_result("setup"), _result("test_suite", "FAIL"), _result("export_canonical"), _result("startup_smoke")],
    )
    assert startup_state == "FAIL"
    assert startup_blockers == ["test_suite:FAIL"]
    assert product_state == "BLOCKED_FOR_PRODUCT_COMPLETION"
    assert "startup_setup_state:FAIL" in product_blockers


def test_skipped_required_gate_blocks_official_startup_setup():
    startup_state, startup_blockers = audit.classify_startup_setup(
        [
            audit.skipped("setup", "setup skipped by audit policy"),
            _result("test_suite"),
            _result("export_canonical"),
            _result("startup_smoke"),
        ]
    )
    assert startup_state == "BLOCKED"
    assert startup_blockers == ["setup:setup skipped by audit policy"]


def test_env_presence_records_only_boolean_values(monkeypatch):
    monkeypatch.setenv("PUBLIC_TEST_KEY", "secret-value")
    observed = audit.env_presence(["PUBLIC_TEST_KEY", "MISSING_TEST_KEY"])
    assert observed == {"PUBLIC_TEST_KEY": True, "MISSING_TEST_KEY": False}
    assert "secret-value" not in repr(observed)


def test_summary_arithmetic_requires_all_seven_repos(tmp_path):
    repos = [
        {
            "repo_id": repo,
            "startup_setup_state": "STARTUP_SETUP_COMPLETE",
            "product_completion_state": "PRODUCT_COMPLETE",
            "command_results": [],
            "head_sha": "a" * 40,
        }
        for repo in audit.REPO_ORDER
    ]
    summary = audit.build_summary("run", tmp_path, repos, tmp_path, tmp_path / "workspace")
    assert summary["startup_setup_certification"] == "PASS"
    assert summary["product_completion_certification"] == "PASS"
    assert summary["arithmetic"]["closed"] is True
    assert summary["arithmetic"]["classified"] == 7
    assert summary["arithmetic"]["counts"] == {"STARTUP_SETUP_COMPLETE": 7}


def test_thehub_has_explicit_commands_without_manifest(tmp_path):
    plan = audit.command_plan("thehub-pr", tmp_path, {}, True, tmp_path / "audit")
    commands = {name: command for name, command, _ in plan}
    assert commands["setup"]
    assert commands["test_suite"]
    assert commands["export_canonical"]
    assert commands["startup_smoke"]
