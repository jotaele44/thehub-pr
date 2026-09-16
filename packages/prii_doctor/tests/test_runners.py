"""Runner-level tests: presence-vs-absence, the not-automatable runner never
performs I/O, and delegate_subprocess stays repo-agnostic across two
differently-shaped validation commands."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import prii_doctor.runners as runners_mod
from prii_doctor.manifest import CheckSpec
from prii_doctor.types import DiagnosabilityClass


def _spec(**overrides) -> CheckSpec:
    defaults: dict = dict(
        id="test_check",
        diagnosability_class=DiagnosabilityClass.PRESENCE_ONLY,
        check={},
        severity_if_absent="advisory",
        operator_action="",
        last_known_state={},
    )
    defaults.update(overrides)
    return CheckSpec(**defaults)


def test_env_var_presence_present_is_info_never_pass(monkeypatch):
    monkeypatch.setenv("PRII_DOCTOR_TEST_VAR", "value")
    spec = _spec(check={"env_var": "PRII_DOCTOR_TEST_VAR"})
    result = runners_mod.run_env_var_presence(spec, Path("."), {})
    assert result.status == "INFO"
    assert result.diagnosability_class == DiagnosabilityClass.PRESENCE_ONLY


def test_env_var_presence_absent_blocking_is_fail(monkeypatch):
    monkeypatch.delenv("PRII_DOCTOR_TEST_VAR", raising=False)
    spec = _spec(check={"env_var": "PRII_DOCTOR_TEST_VAR"}, severity_if_absent="blocking")
    assert runners_mod.run_env_var_presence(spec, Path("."), {}).status == "FAIL"


def test_env_var_presence_absent_advisory_is_warn(monkeypatch):
    monkeypatch.delenv("PRII_DOCTOR_TEST_VAR", raising=False)
    spec = _spec(check={"env_var": "PRII_DOCTOR_TEST_VAR"}, severity_if_absent="advisory")
    assert runners_mod.run_env_var_presence(spec, Path("."), {}).status == "WARN"


def test_file_presence_reachable_vs_unreachable(tmp_path):
    (tmp_path / "present.txt").write_text("hi", encoding="utf-8")

    spec_present = _spec(check={"path": "present.txt"})
    assert runners_mod.run_file_presence(spec_present, tmp_path, {}).status == "INFO"

    spec_absent = _spec(check={"path": "missing.txt"}, severity_if_absent="blocking")
    assert runners_mod.run_file_presence(spec_absent, tmp_path, {}).status == "FAIL"


def test_manual_runner_performs_zero_io(monkeypatch, tmp_path):
    """Regression guard: the not-automatable runner must never touch the
    filesystem, network, or a subprocess -- only echo the manifest's
    recorded last_known_state. Patch subprocess.run to explode and confirm
    the runner still returns cleanly without calling it."""
    def _boom(*_a, **_k):
        raise AssertionError("run_manual performed I/O via subprocess.run")

    monkeypatch.setattr(runners_mod.subprocess, "run", _boom)
    spec = _spec(
        diagnosability_class=DiagnosabilityClass.NOT_AUTOMATABLE,
        check={"type": "manual"},
        last_known_state={"as_of": "2025-03-03", "note": "third-party mirror inactive"},
    )
    result = runners_mod.run_manual(spec, tmp_path, {})
    assert result.status == "INFO"
    assert "2025-03-03" in result.detail
    assert result.diagnosability_class == DiagnosabilityClass.NOT_AUTOMATABLE


def _write_script(tmp_path: Path, name: str, body: str) -> Path:
    script = tmp_path / name
    script.write_text(body, encoding="utf-8")
    return script


@pytest.mark.parametrize(
    "script_body,expect_status",
    [
        # aguayluz-shaped: a table-printing gate CLI that exits 0
        ("print('GATE STATUS')\nprint('G01_SCHEMA PASS')\n", "PASS"),
        # moneysweep-shaped: a bare pass/fail preflight line, nonzero exit
        ("import sys\nprint('preflight: FAIL missing key')\nsys.exit(1)\n", "FAIL"),
    ],
)
def test_delegate_subprocess_is_repo_agnostic(tmp_path, script_body, expect_status):
    """Confirms the runner only ever looks at exit code + output text,
    regardless of how differently two producers shape their own validation
    command's output -- the portability property the whole design relies on."""
    script = _write_script(tmp_path, "fake_validate.py", script_body)
    spec = _spec(
        diagnosability_class=DiagnosabilityClass.LOCAL_DETERMINISTIC,
        check={"type": "delegate_subprocess", "entrypoint_key": "validation_gates"},
    )
    federation_json = {"hub_callable_commands": {"validation_gates": f"{sys.executable} {script}"}}
    result = runners_mod.run_delegate_subprocess(spec, tmp_path, federation_json)
    assert result.status == expect_status
    assert result.diagnosability_class == DiagnosabilityClass.LOCAL_DETERMINISTIC


def test_delegate_subprocess_skips_when_entrypoint_key_unresolvable(tmp_path):
    spec = _spec(
        diagnosability_class=DiagnosabilityClass.LOCAL_DETERMINISTIC,
        check={"type": "delegate_subprocess", "entrypoint_key": "does_not_exist"},
    )
    result = runners_mod.run_delegate_subprocess(spec, tmp_path, {"hub_callable_commands": {}})
    assert result.status == "SKIP"
