"""Tests for gui_parity_status: classify() and summarize()."""

from __future__ import annotations

from hub.gui_parity_status import ProducerGuiParity, classify, summarize


# ── classify() unit tests ───────────────────────────────────────────────────


def test_classify_missing_checkout():
    assert (
        classify(
            checkout_present=False,
            gui_manifest_present=False,
            gui_checker_present=False,
            run_error=None,
            passed=None,
            new=None,
            manifest_issues=None,
            staged_capability_count=0,
        )
        == "missing_checkout"
    )


def test_classify_no_gate_at_all():
    # ovnis-pr / skywatcher-pr / spiderweb-pr's shape on main: checkout present,
    # neither the manifest nor the checker script exists.
    assert (
        classify(
            checkout_present=True,
            gui_manifest_present=False,
            gui_checker_present=False,
            run_error=None,
            passed=None,
            new=None,
            manifest_issues=None,
            staged_capability_count=0,
        )
        == "no_gui_parity_gate"
    )


def test_classify_partial_gate_manifest_without_checker():
    assert (
        classify(
            checkout_present=True,
            gui_manifest_present=True,
            gui_checker_present=False,
            run_error=None,
            passed=None,
            new=None,
            manifest_issues=None,
            staged_capability_count=0,
        )
        == "partial_gui_parity_gate"
    )


def test_classify_partial_gate_checker_without_manifest():
    assert (
        classify(
            checkout_present=True,
            gui_manifest_present=False,
            gui_checker_present=True,
            run_error=None,
            passed=None,
            new=None,
            manifest_issues=None,
            staged_capability_count=0,
        )
        == "partial_gui_parity_gate"
    )


def test_classify_gate_run_failed():
    assert (
        classify(
            checkout_present=True,
            gui_manifest_present=True,
            gui_checker_present=True,
            run_error="TimeoutExpired: ...",
            passed=None,
            new=None,
            manifest_issues=None,
            staged_capability_count=0,
        )
        == "gate_run_failed"
    )


def test_classify_gaps_from_new_candidates():
    assert (
        classify(
            checkout_present=True,
            gui_manifest_present=True,
            gui_checker_present=True,
            run_error=None,
            passed=False,
            new=5,
            manifest_issues=0,
            staged_capability_count=0,
        )
        == "gui_parity_gaps"
    )


def test_classify_gaps_from_manifest_issues_even_if_new_is_zero():
    assert (
        classify(
            checkout_present=True,
            gui_manifest_present=True,
            gui_checker_present=True,
            run_error=None,
            passed=False,
            new=0,
            manifest_issues=3,
            staged_capability_count=0,
        )
        == "gui_parity_gaps"
    )


def test_classify_clean_with_staged_debt():
    # moneysweep-pr's shape before #491: check passes (new=0, manifest_issues=0)
    # but a staged exemption is doing real work.
    assert (
        classify(
            checkout_present=True,
            gui_manifest_present=True,
            gui_checker_present=True,
            run_error=None,
            passed=True,
            new=0,
            manifest_issues=0,
            staged_capability_count=1,
        )
        == "clean_with_staged_debt"
    )


def test_classify_clean():
    assert (
        classify(
            checkout_present=True,
            gui_manifest_present=True,
            gui_checker_present=True,
            run_error=None,
            passed=True,
            new=0,
            manifest_issues=0,
            staged_capability_count=0,
        )
        == "clean"
    )


# ── summarize() ──────────────────────────────────────────────────────────────


def _row(program_id: str, blocker_class: str) -> ProducerGuiParity:
    return ProducerGuiParity(
        program_id=program_id,
        repo=f"jotaele44/{program_id}",
        local_path=program_id,
        checkout_present=True,
        gui_manifest_present=True,
        gui_checker_present=True,
        staged_capability_count=0,
        mode="ratchet",
        current=1,
        mapped=1,
        legacy=0,
        new=0,
        manifest_issues=0,
        passed=True,
        run_error=None,
        blocker_class=blocker_class,
    )


def test_summarize_counts_by_blocker():
    rows = [_row("a", "clean"), _row("b", "clean"), _row("c", "no_gui_parity_gate")]
    summary = summarize(rows)
    assert summary["producer_count"] == 3
    assert summary["clean_count"] == 2
    assert summary["by_blocker"] == {"clean": 2, "no_gui_parity_gate": 1}
    assert [p["program_id"] for p in summary["producers"]] == ["a", "b", "c"]


def test_summarize_empty():
    summary = summarize([])
    assert summary["producer_count"] == 0
    assert summary["clean_count"] == 0
    assert summary["by_blocker"] == {}
    assert summary["producers"] == []
