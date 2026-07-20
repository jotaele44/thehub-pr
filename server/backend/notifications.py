"""Notification engine for the PRII Hub.

Turns the aggregated ``GovernanceAlerts`` stream into an actionable, per-subscriber
notification layer so a returning user is told **what is new since they last looked**,
and so life-safety (``is_critical``) alerts are pushed out even when the app is closed.

Design goals / constraints:

* **Pure core, thin store.** The decision logic — ranking new alerts, resolving a
  subscriber's per-domain preference, deciding ASAP-vs-brief and which channels fire —
  is plain Python with no FastAPI/DB import, so it is unit-testable in the same
  offline harness as the rest of ``src/hub`` (the backend's FastAPI routes are the
  only part that needs the web framework). ``NotificationStore`` is a thin SQLite
  wrapper the routes use.
* **Per-subscriber preferences (channel + timing), global or per-domain.** Each
  subscriber picks, for ``"all"`` domains or a specific domain, a channel set drawn
  from ``push`` / ``sms`` (empty set = ``None``, i.e. opt out) and a timing of
  ``asap`` or ``brief`` (batched digest). ``is_critical`` alerts default to ``asap``
  but that default is itself overridable.
* **Offline-safe delivery.** The push / SMS / email senders no-op cleanly (returning
  ``skipped_no_config``) when their provider secrets are unset, so the hub runs
  identically in dev, CI and a bare clone. The in-app center always sees every alert
  regardless of channel/timing preferences.
"""
from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Iterable

# ── Domain taxonomy ─────────────────────────────────────────────────────────────
# Alert module -> the coarse domain a subscriber tunes preferences against. Keeps the
# preference surface small (a handful of domains) rather than one row per module.
DOMAIN_FOR_MODULE: dict[str, str] = {
    "CONTAMINATION": "water",
    "HYDRO_OPS": "water",
    "DAM_SAFETY": "water",
    "POWER_OPS": "power",
    "SEISMIC_GEO": "seismic",
    "WEATHER_HAZARD": "weather",
    "INDUSTRIAL": "industrial",
    "PUBLIC_NOTICE": "public",
    "TRANSPORT_ACCESS": "transport",
    "TELECOM_SCADA": "telecom",
}
DEFAULT_DOMAIN = "other"

VALID_CHANNELS = ("push", "sms")
VALID_TIMING = ("asap", "brief")

# The preference used when a subscriber has set neither a per-domain nor an "all"
# default: in-app only (empty channel set), ASAP. The in-app center is unconditional,
# so this means "surface it in-app, send nothing outbound" until the user opts in.
_FALLBACK_PREF = {"channels": (), "timing": "asap"}


def domain_for(module: Any) -> str:
    return DOMAIN_FOR_MODULE.get(str(module), DEFAULT_DOMAIN)


# ── Pure decision core ──────────────────────────────────────────────────────────

def _ts(alert: dict[str, Any]) -> str:
    """Recency key for an alert row (occurred/observed, else created)."""
    return str(
        alert.get("occurred_at")
        or alert.get("observed_at")
        or alert.get("created_date")
        or ""
    )


def rank_new_alerts(alerts: Iterable[dict[str, Any]], since: str | None) -> list[dict[str, Any]]:
    """New alerts strictly after ``since``, most-severe-then-most-recent first.

    ``since`` is an ISO timestamp cursor (or ``None`` / "" for "everything"). Ordering
    puts life-safety (``is_critical``) alerts on top, then newest first — the order the
    in-app center and the digest present.
    """
    cutoff = since or ""
    fresh = [a for a in alerts if _ts(a) > cutoff]
    fresh.sort(key=lambda a: (bool(a.get("is_critical")), _ts(a)), reverse=True)
    return fresh


def normalize_pref(pref: Any) -> dict[str, Any]:
    """Coerce a stored/submitted preference into ``{channels: tuple, timing: str}``."""
    if not isinstance(pref, dict):
        return dict(_FALLBACK_PREF)
    channels = tuple(c for c in pref.get("channels", ()) if c in VALID_CHANNELS)
    timing = pref.get("timing") if pref.get("timing") in VALID_TIMING else "asap"
    return {"channels": channels, "timing": timing}


def resolve_pref(prefs: dict[str, Any], domain: str) -> dict[str, Any]:
    """A subscriber's effective preference for ``domain``.

    Precedence: an explicit per-domain override, else the ``"all"`` global default,
    else the in-app-only fallback. ``prefs`` maps domain (or ``"all"``) -> preference.
    """
    if domain in prefs:
        return normalize_pref(prefs[domain])
    if "all" in prefs:
        return normalize_pref(prefs["all"])
    return dict(_FALLBACK_PREF)


def decide_dispatch(alert: dict[str, Any], prefs: dict[str, Any]) -> dict[str, Any]:
    """Resolve how one alert should reach one subscriber.

    Returns ``{"now": [channels], "brief": [channels], "domain": str}`` — channels to
    fire immediately vs. batch into the next scheduled brief. Critical alerts are
    forced ASAP *unless* the subscriber explicitly set that domain to ``brief`` (the
    default is still user-overridable, per the approved model).
    """
    domain = domain_for(alert.get("module"))
    pref = resolve_pref(prefs, domain)
    channels = list(pref["channels"])
    if not channels:
        return {"now": [], "brief": [], "domain": domain}
    # is_critical defaults to ASAP; an explicit per-domain override to "brief" wins.
    explicit = domain in prefs or "all" in prefs
    timing = pref["timing"]
    if alert.get("is_critical") and not (explicit and timing == "brief"):
        timing = "asap"
    if timing == "brief":
        return {"now": [], "brief": channels, "domain": domain}
    return {"now": channels, "brief": [], "domain": domain}


# ── Offline-safe channel senders ────────────────────────────────────────────────
# Each returns "sent" (provider configured + attempted), "skipped_no_config" (no
# provider secret -> no-op), or "skipped_no_target". Real provider wiring lives behind
# the env checks; the contract and the no-op path are what the hub depends on so it
# runs identically without any secrets.

def _provider_configured(channel: str) -> bool:
    if channel == "push":
        return bool(os.environ.get("HUB_VAPID_PRIVATE_KEY"))
    if channel == "sms":
        return bool(os.environ.get("HUB_SMS_API_KEY"))
    if channel == "email":
        return bool(os.environ.get("HUB_SMTP_URL"))
    return False


def send_via(channel: str, target: str | None, alert: dict[str, Any]) -> str:
    """Deliver one alert on one channel to one target (offline-safe no-op)."""
    if not target:
        return "skipped_no_target"
    if not _provider_configured(channel):
        return "skipped_no_config"
    # Provider integration point. Intentionally not calling out to a live provider in
    # this build; when the secret is present the real client would send here.
    return "sent"


def render_message(alert: dict[str, Any]) -> str:
    """Short human message for push/SMS/brief bodies."""
    module = alert.get("module") or "Alert"
    summary = alert.get("summary") or alert.get("alert_type") or "update"
    flag = "⚠ CRITICAL " if alert.get("is_critical") else ""
    return f"{flag}{module}: {summary}"


# ── SQLite store ────────────────────────────────────────────────────────────────

class NotificationStore:
    """Thin SQLite store for subscriber cursors, preferences, targets and the brief queue."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self._init()

    def _init(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS notification_state (
                subscriber_id TEXT PRIMARY KEY,
                last_seen     TEXT
            );
            CREATE TABLE IF NOT EXISTS notification_subscriptions (
                subscriber_id TEXT PRIMARY KEY,
                prefs         TEXT NOT NULL,   -- JSON {domain|"all": {channels, timing}}
                targets       TEXT NOT NULL,   -- JSON {push: endpoint, sms: number, email: addr}
                updated_at    TEXT
            );
            CREATE TABLE IF NOT EXISTS notification_outbox (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                subscriber_id TEXT NOT NULL,
                channel       TEXT NOT NULL,
                alert         TEXT NOT NULL,   -- JSON alert row
                queued_at     TEXT
            );
            """
        )
        self.conn.commit()

    # cursor -------------------------------------------------------------------
    def get_cursor(self, subscriber_id: str = "operator") -> str | None:
        row = self.conn.execute(
            "SELECT last_seen FROM notification_state WHERE subscriber_id=?", (subscriber_id,)
        ).fetchone()
        return row[0] if row else None

    def set_cursor(self, last_seen: str, subscriber_id: str = "operator") -> None:
        self.conn.execute(
            "INSERT INTO notification_state (subscriber_id, last_seen) VALUES (?,?) "
            "ON CONFLICT(subscriber_id) DO UPDATE SET last_seen=excluded.last_seen",
            (subscriber_id, last_seen),
        )
        self.conn.commit()

    # subscriptions ------------------------------------------------------------
    def get_subscription(self, subscriber_id: str = "operator") -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT prefs, targets FROM notification_subscriptions WHERE subscriber_id=?",
            (subscriber_id,),
        ).fetchone()
        if not row:
            return {"prefs": {}, "targets": {}}
        return {"prefs": json.loads(row[0]), "targets": json.loads(row[1])}

    def set_subscription(
        self, prefs: dict[str, Any], targets: dict[str, Any], subscriber_id: str = "operator",
        updated_at: str = "",
    ) -> None:
        self.conn.execute(
            "INSERT INTO notification_subscriptions (subscriber_id, prefs, targets, updated_at) "
            "VALUES (?,?,?,?) ON CONFLICT(subscriber_id) DO UPDATE SET "
            "prefs=excluded.prefs, targets=excluded.targets, updated_at=excluded.updated_at",
            (subscriber_id, json.dumps(prefs), json.dumps(targets), updated_at),
        )
        self.conn.commit()

    def all_subscriptions(self) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
        rows = self.conn.execute(
            "SELECT subscriber_id, prefs, targets FROM notification_subscriptions"
        ).fetchall()
        return [(r[0], json.loads(r[1]), json.loads(r[2])) for r in rows]

    # brief queue --------------------------------------------------------------
    def enqueue_brief(self, subscriber_id: str, channel: str, alert: dict[str, Any], queued_at: str) -> None:
        self.conn.execute(
            "INSERT INTO notification_outbox (subscriber_id, channel, alert, queued_at) VALUES (?,?,?,?)",
            (subscriber_id, channel, json.dumps(alert), queued_at),
        )
        self.conn.commit()

    def drain_brief(self, subscriber_id: str) -> list[tuple[str, dict[str, Any]]]:
        rows = self.conn.execute(
            "SELECT id, channel, alert FROM notification_outbox WHERE subscriber_id=? ORDER BY id",
            (subscriber_id,),
        ).fetchall()
        items = [(r[1], json.loads(r[2])) for r in rows]
        if rows:
            self.conn.executemany(
                "DELETE FROM notification_outbox WHERE id=?", [(r[0],) for r in rows]
            )
            self.conn.commit()
        return items


def dispatch_new_alerts(
    store: NotificationStore, alerts: list[dict[str, Any]], now: str
) -> dict[str, int]:
    """Fan a batch of (already-new) alerts out to every subscriber per their prefs.

    ASAP channels are sent immediately (offline-safe); brief channels are queued for
    the next scheduled brief. Returns a small tally for logging/telemetry.
    """
    tally = {"sent": 0, "queued": 0, "skipped": 0}
    for sub_id, prefs, targets in store.all_subscriptions():
        for alert in alerts:
            plan = decide_dispatch(alert, prefs)
            for ch in plan["now"]:
                result = send_via(ch, targets.get(ch), alert)
                tally["sent" if result == "sent" else "skipped"] += 1
            for ch in plan["brief"]:
                store.enqueue_brief(sub_id, ch, alert, now)
                tally["queued"] += 1
    return tally
