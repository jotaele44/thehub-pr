#!/usr/bin/env python3
"""Fan newly-ingested alerts out to subscribers (push/SMS), then advance the cursor.

Federation hop 3: after `hub ingest` lands fresh GovernanceAlerts in data/hub.db, this
script pushes what is new since the last dispatch out to each subscriber per their
per-domain channel/timing preferences (server/backend/notifications.py). Life-safety
(`is_critical`) alerts go ASAP; others may be batched into a scheduled brief.

Offline-safe: the channel senders no-op cleanly when their provider secrets
(HUB_VAPID_PRIVATE_KEY / HUB_SMS_API_KEY / HUB_SMTP_URL) are unset, so this runs
identically in CI and a bare clone — it simply advances the cursor and reports skips.

Usage:
    python scripts/dispatch_notifications.py            # dispatch new alerts
    python scripts/dispatch_notifications.py --brief     # send queued scheduled briefs
    python scripts/dispatch_notifications.py --db data/hub.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.backend import notifications as notif  # noqa: E402

# A reserved subscriber id holding the *dispatch* cursor (distinct from any human
# subscriber's in-app "last seen" cursor), so outbound delivery advances independently.
_DISPATCH_CURSOR = "__dispatch__"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_alerts(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT data FROM entities WHERE entity_type='GovernanceAlerts' "
        "ORDER BY updated_at DESC LIMIT 5000"
    ).fetchall()
    return [json.loads(r[0]) for r in rows]


def dispatch(db: Path, now: str) -> dict:
    conn = sqlite3.connect(db)
    try:
        store = notif.NotificationStore(conn)
        cursor = store.get_cursor(_DISPATCH_CURSOR)
        fresh = notif.rank_new_alerts(_load_alerts(conn), cursor)
        tally = notif.dispatch_new_alerts(store, fresh, now)
        if fresh:
            newest = max(notif._ts(a) for a in fresh)  # advance past the newest sent
            store.set_cursor(newest, _DISPATCH_CURSOR)
        tally["new_alerts"] = len(fresh)
        tally["critical"] = sum(1 for a in fresh if a.get("is_critical"))
        return tally
    finally:
        conn.close()


def run_briefs(db: Path) -> dict:
    conn = sqlite3.connect(db)
    try:
        store = notif.NotificationStore(conn)
        sent = 0
        for sub_id, _prefs, targets in store.all_subscriptions():
            for channel, alert in store.drain_brief(sub_id):
                notif.send_via(channel, targets.get(channel), alert)
                sent += 1
        return {"brief_items_sent": sent}
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(REPO_ROOT / "data" / "hub.db"))
    ap.add_argument("--brief", action="store_true", help="send queued scheduled briefs instead")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        print(f"no hub.db at {db} — nothing to dispatch")
        return 0

    result = run_briefs(db) if args.brief else dispatch(db, _now())
    print("notification dispatch:", json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
