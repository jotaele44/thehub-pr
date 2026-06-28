"""Rollup tests: loading producer reports from a workspace root."""
import json

from hub.maintenance import REPORT_RELPATH, build_rollup
from hub.registry import load_registry

REGISTRY = "registry/producers.yaml"


def _write_report(root, repo, **overrides):
    report = {
        "repo": repo,
        "maintenance_version": "0.1.0",
        "mode": "audit",
        "generated_at": "2026-01-01T00:00:00Z",
        "findings_count": 0,
        "critical_count": 0,
        "promotion_blocked": False,
        "findings": [],
    }
    report.update(overrides)
    path = root / repo / REPORT_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report))
    return path


def test_all_missing_blocks(tmp_path):
    reg = load_registry(REGISTRY)
    rollup = build_rollup(reg, tmp_path)
    assert rollup["producer_count"] == len(reg.producers)
    assert rollup["reports_missing"] == len(reg.producers)
    assert rollup["promotion_blocked"] is True


def test_one_present_report_counts(tmp_path):
    reg = load_registry(REGISTRY)
    _write_report(tmp_path, "aguayluz-pr", findings_count=3, critical_count=0)
    rollup = build_rollup(reg, tmp_path)
    assert rollup["reports_missing"] == len(reg.producers) - 1
    status = rollup["repo_status"]["aguayluz-pr"]
    assert status["report_present"] is True
    assert status["report_valid"] is True
    assert status["findings_count"] == 3
    assert rollup["findings_count"] == 3


def test_critical_finding_blocks_rollup(tmp_path):
    reg = load_registry(REGISTRY)
    for p in reg.producers:
        _write_report(tmp_path, p.program_id)
    # Inject a critical report for one producer.
    _write_report(tmp_path, "skywatcher-pr", critical_count=1, promotion_blocked=True)
    rollup = build_rollup(reg, tmp_path)
    assert rollup["reports_missing"] == 0
    assert rollup["critical_count"] == 1
    assert rollup["promotion_blocked"] is True


def test_invalid_report_is_flagged(tmp_path):
    reg = load_registry(REGISTRY)
    for p in reg.producers:
        _write_report(tmp_path, p.program_id)
    # Corrupt one report with a bad enum.
    bad_path = tmp_path / "ovnis-pr" / REPORT_RELPATH
    data = json.loads(bad_path.read_text())
    data["mode"] = "totally-invalid-mode"
    bad_path.write_text(json.dumps(data))
    rollup = build_rollup(reg, tmp_path)
    assert rollup["reports_invalid"] == 1
    assert rollup["repo_status"]["ovnis-pr"]["report_valid"] is False
    assert rollup["promotion_blocked"] is True
