"""Engine-level tests: missing-manifest handling, and an end-to-end run for
both a not-automatable and a presence-only check."""

from __future__ import annotations

import json
from pathlib import Path

from prii_doctor.engine import run


def _write_manifest(repo_root: Path, checks: list[dict], validation_entrypoint: str | None = None) -> None:
    fed_dir = repo_root / ".federation"
    fed_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "prii.doctor-checks/v1",
        "repository": "test/repo",
        "checks": checks,
    }
    if validation_entrypoint is not None:
        payload["validation_entrypoint"] = validation_entrypoint
    (fed_dir / "doctor-checks.json").write_text(json.dumps(payload), encoding="utf-8")


def test_no_manifest_returns_empty_report(tmp_path):
    report = run(tmp_path)
    assert report.results == []


def test_manual_check_end_to_end(tmp_path):
    _write_manifest(
        tmp_path,
        [
            {
                "id": "waf_blocked_source",
                "diagnosability_class": "not-automatable",
                "check": {"type": "manual"},
                "last_known_state": {"as_of": "2025-03-03", "note": "mirror inactive"},
            }
        ],
    )
    report = run(tmp_path)
    assert len(report.results) == 1
    assert report.results[0].status == "INFO"
    assert report.results[0].diagnosability_class.value == "not-automatable"


def test_env_var_check_end_to_end(tmp_path, monkeypatch):
    monkeypatch.delenv("SOME_TEST_KEY", raising=False)
    _write_manifest(
        tmp_path,
        [
            {
                "id": "some_test_key",
                "diagnosability_class": "presence-only",
                "severity_if_absent": "blocking",
                "check": {"type": "env_var_presence", "env_var": "SOME_TEST_KEY"},
            }
        ],
    )
    report = run(tmp_path)
    assert report.results[0].status == "FAIL"
    assert not report.all_blocking_passed


def test_delegate_subprocess_defaults_entrypoint_key_from_manifest(tmp_path):
    """A delegate_subprocess check with no explicit entrypoint_key should
    fall back to the manifest's top-level validation_entrypoint."""
    (tmp_path / "federation.json").write_text(
        json.dumps({"hub_callable_commands": {"validation_gates": "echo ok"}}), encoding="utf-8"
    )
    _write_manifest(
        tmp_path,
        [
            {
                "id": "outputs_schema_validation",
                "diagnosability_class": "local-deterministic",
                "check": {"type": "delegate_subprocess"},
            }
        ],
        validation_entrypoint="validation_gates",
    )
    report = run(tmp_path)
    assert report.results[0].status == "PASS"
