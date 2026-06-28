"""Promotion-gate policy tests."""
from hub.maintenance.gate import compute_gate


def _rollup(**status_by_repo):
    return {
        "reports_missing": 0,
        "reports_invalid": 0,
        "repo_status": status_by_repo,
    }


def test_clean_rollup_passes():
    rollup = _rollup(**{"aguayluz-pr": {"critical_count": 0, "promotion_blocked": False}})
    gate = compute_gate(rollup)
    assert gate["promotion_blocked"] is False
    assert gate["blockers"] == []


def test_critical_finding_blocks():
    rollup = _rollup(**{"aguayluz-pr": {"critical_count": 2, "promotion_blocked": False}})
    gate = compute_gate(rollup)
    assert gate["promotion_blocked"] is True
    assert any("critical" in b for b in gate["blockers"])


def test_producer_self_block_propagates():
    rollup = _rollup(**{"ovnis-pr": {"critical_count": 0, "promotion_blocked": True}})
    assert compute_gate(rollup)["promotion_blocked"] is True


def test_missing_report_blocks():
    rollup = {"reports_missing": 1, "reports_invalid": 0, "repo_status": {}}
    gate = compute_gate(rollup)
    assert gate["promotion_blocked"] is True
    assert any("missing" in b for b in gate["blockers"])


def test_invalid_report_blocks():
    rollup = {"reports_missing": 0, "reports_invalid": 1, "repo_status": {}}
    assert compute_gate(rollup)["promotion_blocked"] is True
