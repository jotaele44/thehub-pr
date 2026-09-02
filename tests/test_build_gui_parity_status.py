"""Tests for build_gui_parity_status: build() against fake producer checkouts.

classify()'s pure logic is covered in test_gui_parity_status.py; this file
covers the filesystem/subprocess plumbing around it — locating a producer's
checkout, detecting the manifest/checker pair, and actually running a
checker script and parsing its report.
"""

from __future__ import annotations

import importlib.util
import json
import stat
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Loaded by path: scripts/ is not a package, so a plain import will not find it.
_spec = importlib.util.spec_from_file_location(
    "build_gui_parity_status", REPO_ROOT / "scripts" / "build_gui_parity_status.py"
)
bgps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bgps)


# %s placeholders (not str.format): the payload itself is JSON full of braces,
# which str.format would try to parse as replacement fields.
_FAKE_CHECKER = """#!/usr/bin/env python3
import argparse, json, sys
p = argparse.ArgumentParser()
p.add_argument("--report", required=True)
p.add_argument("--repo-root", default=None)
args = p.parse_args()
report = json.loads(%r)
with open(args.report, "w") as f:
    json.dump(report, f)
sys.exit(0 if report["passed"] else 1)
"""


def _make_registry(local_path: str):
    from hub.registry import Producer, Registry

    return Registry(
        hub="thehub-pr",
        schema_version="hub_registry_v1",
        producers=[
            Producer(
                program_id="test-producer",
                repo="jotaele44/test-producer",
                role="test_node",
                local_path=local_path,
            )
        ],
    )


def _write_registry_yaml(tmp_path: Path, local_path: str) -> Path:
    registry_path = tmp_path / "producers.yaml"
    registry_path.write_text(
        "schema_version: hub_registry_v1\n"
        "hub: thehub-pr\n"
        "producers:\n"
        "  - program_id: test-producer\n"
        "    repo: jotaele44/test-producer\n"
        "    role: test_node\n"
        f"    local_path: {local_path}\n"
    )
    return registry_path


def _install_fake_checker(
    producer_dir: Path,
    *,
    passed: bool,
    current: int,
    mapped: int,
    legacy: int,
    new: int,
    manifest_issues: int,
    capabilities: list | None = None,
) -> None:
    scripts_dir = producer_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    checker = scripts_dir / "check_gui_parity.py"
    report = {
        "mode": "ratchet",
        "passed": passed,
        "summary": {
            "current_candidates": current,
            "mapped_candidates": mapped,
            "legacy_gaps": legacy,
            "new_gaps": new,
            "manifest_issues": manifest_issues,
        },
    }
    checker.write_text(_FAKE_CHECKER % json.dumps(report))
    checker.chmod(checker.stat().st_mode | stat.S_IEXEC)
    (producer_dir / ".federation").mkdir(exist_ok=True)
    (producer_dir / ".federation" / "gui-capabilities.json").write_text(
        json.dumps({"capabilities": capabilities or []})
    )


def test_build_missing_checkout(tmp_path):
    registry_path = _write_registry_yaml(tmp_path, "nonexistent")
    summary = bgps.build(registry_path, tmp_path, "2026-01-01T00:00:00+00:00")
    p = summary["producers"][0]
    assert p["blocker_class"] == "missing_checkout"
    assert p["checkout_present"] is False


def test_build_no_gate_at_all(tmp_path):
    producer_dir = tmp_path / "prod"
    producer_dir.mkdir()
    registry_path = _write_registry_yaml(tmp_path, "prod")
    summary = bgps.build(registry_path, tmp_path, "2026-01-01T00:00:00+00:00")
    p = summary["producers"][0]
    assert p["blocker_class"] == "no_gui_parity_gate"
    assert p["gui_manifest_present"] is False
    assert p["gui_checker_present"] is False


def test_build_partial_gate_manifest_without_checker(tmp_path):
    producer_dir = tmp_path / "prod"
    (producer_dir / ".federation").mkdir(parents=True)
    (producer_dir / ".federation" / "gui-capabilities.json").write_text("{}")
    registry_path = _write_registry_yaml(tmp_path, "prod")
    summary = bgps.build(registry_path, tmp_path, "2026-01-01T00:00:00+00:00")
    p = summary["producers"][0]
    assert p["blocker_class"] == "partial_gui_parity_gate"


def test_build_runs_real_checker_and_parses_report_clean(tmp_path):
    producer_dir = tmp_path / "prod"
    _install_fake_checker(
        producer_dir,
        passed=True,
        current=10,
        mapped=10,
        legacy=0,
        new=0,
        manifest_issues=0,
    )
    registry_path = _write_registry_yaml(tmp_path, "prod")
    summary = bgps.build(registry_path, tmp_path, "2026-01-01T00:00:00+00:00")
    p = summary["producers"][0]
    assert p["blocker_class"] == "clean"
    assert p["mode"] == "ratchet"
    assert p["current"] == 10
    assert p["new"] == 0
    assert p["run_error"] is None


def test_build_runs_real_checker_and_reports_gaps(tmp_path):
    producer_dir = tmp_path / "prod"
    _install_fake_checker(
        producer_dir,
        passed=False,
        current=10,
        mapped=7,
        legacy=1,
        new=2,
        manifest_issues=0,
    )
    registry_path = _write_registry_yaml(tmp_path, "prod")
    summary = bgps.build(registry_path, tmp_path, "2026-01-01T00:00:00+00:00")
    p = summary["producers"][0]
    assert p["blocker_class"] == "gui_parity_gaps"
    assert p["new"] == 2


def test_build_reports_staged_debt_when_checker_passes(tmp_path):
    producer_dir = tmp_path / "prod"
    _install_fake_checker(
        producer_dir,
        passed=True,
        current=5,
        mapped=5,
        legacy=0,
        new=0,
        manifest_issues=0,
        capabilities=[{"id": "x", "status": "staged"}, {"id": "y", "status": "active"}],
    )
    registry_path = _write_registry_yaml(tmp_path, "prod")
    summary = bgps.build(registry_path, tmp_path, "2026-01-01T00:00:00+00:00")
    p = summary["producers"][0]
    assert p["blocker_class"] == "clean_with_staged_debt"
    assert p["staged_capability_count"] == 1


def test_build_handles_checker_that_never_writes_a_report(tmp_path):
    producer_dir = tmp_path / "prod"
    scripts_dir = producer_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    # A checker that exits without ever writing --report — e.g. a crash before
    # the write. Must not be silently mistaken for a clean pass.
    (scripts_dir / "check_gui_parity.py").write_text(
        "#!/usr/bin/env python3\nimport sys\nsys.exit(1)\n"
    )
    (producer_dir / ".federation").mkdir()
    (producer_dir / ".federation" / "gui-capabilities.json").write_text("{}")
    registry_path = _write_registry_yaml(tmp_path, "prod")
    summary = bgps.build(registry_path, tmp_path, "2026-01-01T00:00:00+00:00")
    p = summary["producers"][0]
    assert p["blocker_class"] == "gate_run_failed"
    assert p["run_error"] is not None
