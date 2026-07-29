"""Tests for the Hub notification engine (server/backend/notifications.py).

Pure logic + SQLite store — no FastAPI dependency, so this runs in the standard
offline test harness.
"""
from __future__ import annotations

import os
import sqlite3

from server.backend import notifications as notif


def _alert(module, is_critical=False, ts="2026-07-19T10:00:00Z", summary="x"):
    return {"module": module, "is_critical": is_critical, "occurred_at": ts, "summary": summary}


# ── ranking ──────────────────────────────────────────────────────────────────────

def test_rank_filters_by_cursor_and_orders_critical_first():
    alerts = [
        _alert("HYDRO_OPS", False, "2026-07-19T09:00:00Z"),
        _alert("SEISMIC_GEO", True, "2026-07-19T08:00:00Z"),   # older but critical
        _alert("WEATHER_HAZARD", False, "2026-07-18T00:00:00Z"),  # before cursor
    ]
    fresh = notif.rank_new_alerts(alerts, "2026-07-19T00:00:00Z")
    assert len(fresh) == 2  # the pre-cursor one is dropped
    assert fresh[0]["module"] == "SEISMIC_GEO"  # critical ranks first


def test_rank_none_cursor_returns_all():
    assert len(notif.rank_new_alerts([_alert("HYDRO_OPS"), _alert("SEISMIC_GEO")], None)) == 2


# ── preference resolution ─────────────────────────────────────────────────────────

def test_resolve_pref_per_domain_overrides_global():
    prefs = {"all": {"channels": ["push"], "timing": "asap"},
             "water": {"channels": ["sms"], "timing": "brief"}}
    assert notif.resolve_pref(prefs, "water") == {"channels": ("sms",), "timing": "brief"}
    assert notif.resolve_pref(prefs, "seismic") == {"channels": ("push",), "timing": "asap"}


def test_resolve_pref_fallback_is_inapp_only():
    assert notif.resolve_pref({}, "seismic") == {"channels": (), "timing": "asap"}


def test_normalize_drops_invalid_channels_and_timing():
    p = notif.normalize_pref({"channels": ["push", "carrier-pigeon"], "timing": "whenever"})
    assert p == {"channels": ("push",), "timing": "asap"}


# ── dispatch decision ─────────────────────────────────────────────────────────────

def test_none_channel_skips():
    plan = notif.decide_dispatch(_alert("HYDRO_OPS"), {"all": {"channels": [], "timing": "asap"}})
    assert plan["now"] == [] and plan["brief"] == []


def test_critical_forces_asap_over_global_brief():
    # global timing is brief, but a critical alert with no explicit per-domain brief -> ASAP
    prefs = {"all": {"channels": ["push", "sms"], "timing": "asap"}}
    plan = notif.decide_dispatch(_alert("SEISMIC_GEO", is_critical=True), prefs)
    assert set(plan["now"]) == {"push", "sms"} and plan["brief"] == []


def test_explicit_domain_brief_overrides_critical_asap():
    prefs = {"seismic": {"channels": ["sms"], "timing": "brief"}}
    plan = notif.decide_dispatch(_alert("SEISMIC_GEO", is_critical=True), prefs)
    assert plan["now"] == [] and plan["brief"] == ["sms"]


def test_noncritical_brief_queues():
    prefs = {"all": {"channels": ["push"], "timing": "brief"}}
    plan = notif.decide_dispatch(_alert("HYDRO_OPS"), prefs)
    assert plan["brief"] == ["push"] and plan["now"] == []


def test_domain_for_module():
    assert notif.domain_for("SEISMIC_GEO") == "seismic"
    assert notif.domain_for("CONTAMINATION") == "water"
    assert notif.domain_for("MYSTERY") == "other"


# ── senders are offline-safe ──────────────────────────────────────────────────────

def test_send_via_no_config_is_noop():
    for key in ("HUB_VAPID_PRIVATE_KEY", "HUB_SMS_API_KEY"):
        os.environ.pop(key, None)
    assert notif.send_via("push", "endpoint", _alert("X")) == "skipped_no_config"
    assert notif.send_via("sms", "+1787", _alert("X")) == "skipped_no_config"


def test_send_via_no_target():
    assert notif.send_via("push", None, _alert("X")) == "skipped_no_target"


# ── store + end-to-end dispatch ───────────────────────────────────────────────────

def _store():
    return notif.NotificationStore(sqlite3.connect(":memory:"))


def test_store_cursor_roundtrip():
    s = _store()
    assert s.get_cursor("operator") is None
    s.set_cursor("2026-07-19T10:00:00Z", "operator")
    assert s.get_cursor("operator") == "2026-07-19T10:00:00Z"


def test_store_subscription_roundtrip():
    s = _store()
    s.set_subscription({"all": {"channels": ["sms"], "timing": "asap"}}, {"sms": "+1787"}, "op", "t")
    sub = s.get_subscription("op")
    assert sub["prefs"]["all"]["channels"] == ["sms"]
    assert sub["targets"]["sms"] == "+1787"


def test_dispatch_new_alerts_queues_brief_and_counts():
    s = _store()
    s.set_subscription({"all": {"channels": ["push"], "timing": "brief"}}, {"push": "ep"}, "op", "t")
    tally = notif.dispatch_new_alerts(s, [_alert("HYDRO_OPS")], "2026-07-19T11:00:00Z")
    assert tally["queued"] == 1
    drained = s.drain_brief("op")
    assert len(drained) == 1 and drained[0][0] == "push"
    assert s.drain_brief("op") == []  # drained once


def test_dispatch_critical_asap_no_config_counts_skipped():
    s = _store()
    s.set_subscription({"all": {"channels": ["sms"], "timing": "asap"}}, {"sms": "+1"}, "op", "t")
    os.environ.pop("HUB_SMS_API_KEY", None)
    tally = notif.dispatch_new_alerts(s, [_alert("SEISMIC_GEO", is_critical=True)], "t")
    assert tally["skipped"] == 1 and tally["sent"] == 0
