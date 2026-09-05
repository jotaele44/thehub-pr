"""The central invariant this whole design exists to guarantee: a
CheckResult's status must be legal for its diagnosability_class -- most
importantly, no non-local-deterministic class may ever report PASS."""

from __future__ import annotations

import pytest

from prii_doctor.types import CheckReport, CheckResult, DiagnosabilityClass, status_allowed

# A clean, unambiguous outcome legitimately earns PASS for these two classes:
# local-deterministic (the doctor computed a real answer) and
# live-probe-best-effort (the live call reached the source and got a clean
# 2xx). Every other class -- presence-only, not-automatable -- can never
# report PASS, because presence was never validity and "not automatable"
# means no check ran at all.
_CLASSES_THAT_MAY_PASS = {DiagnosabilityClass.LOCAL_DETERMINISTIC, DiagnosabilityClass.LIVE_PROBE_BEST_EFFORT}


@pytest.mark.parametrize("diagnosability_class", list(DiagnosabilityClass))
def test_pass_is_illegal_outside_local_deterministic_and_live_probe(diagnosability_class):
    if diagnosability_class in _CLASSES_THAT_MAY_PASS:
        CheckResult("x", diagnosability_class, "PASS")  # legal -- must not raise
        return
    assert not status_allowed(diagnosability_class, "PASS")
    with pytest.raises(ValueError):
        CheckResult("x", diagnosability_class, "PASS")


def test_not_automatable_only_ever_info():
    assert status_allowed(DiagnosabilityClass.NOT_AUTOMATABLE, "INFO")
    for bad in ("PASS", "WARN", "FAIL", "SKIP"):
        assert not status_allowed(DiagnosabilityClass.NOT_AUTOMATABLE, bad)
        with pytest.raises(ValueError):
            CheckResult("x", DiagnosabilityClass.NOT_AUTOMATABLE, bad)


def test_presence_only_absent_maps_to_fail_or_warn_never_pass():
    assert status_allowed(DiagnosabilityClass.PRESENCE_ONLY, "FAIL")
    assert status_allowed(DiagnosabilityClass.PRESENCE_ONLY, "WARN")
    assert status_allowed(DiagnosabilityClass.PRESENCE_ONLY, "INFO")
    assert not status_allowed(DiagnosabilityClass.PRESENCE_ONLY, "PASS")
    assert not status_allowed(DiagnosabilityClass.PRESENCE_ONLY, "SKIP")


def test_live_probe_ambiguity_maps_to_warn_never_a_bare_fail_for_ambiguous_signals():
    # PASS/WARN/FAIL are all legal for live-probe-best-effort (runners.py
    # decides which, based on how unambiguous the failure was) -- but SKIP
    # and INFO are not, since a live probe either ran or the check type is
    # wrong for this class.
    assert status_allowed(DiagnosabilityClass.LIVE_PROBE_BEST_EFFORT, "PASS")
    assert status_allowed(DiagnosabilityClass.LIVE_PROBE_BEST_EFFORT, "WARN")
    assert status_allowed(DiagnosabilityClass.LIVE_PROBE_BEST_EFFORT, "FAIL")
    assert not status_allowed(DiagnosabilityClass.LIVE_PROBE_BEST_EFFORT, "INFO")
    assert not status_allowed(DiagnosabilityClass.LIVE_PROBE_BEST_EFFORT, "SKIP")


def test_report_helpers():
    ok = CheckResult("a", DiagnosabilityClass.LOCAL_DETERMINISTIC, "PASS")
    bad = CheckResult("b", DiagnosabilityClass.LOCAL_DETERMINISTIC, "FAIL")
    report = CheckReport(results=[ok, bad])
    assert not report.all_blocking_passed
    assert report.by_id("a") is ok
    assert report.by_id("missing") is None
    assert report.as_rows() == [
        ("a", "local-deterministic", "PASS", ""),
        ("b", "local-deterministic", "FAIL", ""),
    ]
