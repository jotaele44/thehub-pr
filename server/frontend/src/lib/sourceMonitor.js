// Source Monitor (ADR 0011): shared constants and freshness logic for the
// read-only MonitoredSources views. Rows are written by `hub source-monitor`
// (src/hub/source_monitor.py) and loaded by `hub ingest`.
//
// Freshness is PRODUCER-LEVEL. No producer registry records when each source was
// last polled, so the only timestamp is the producer's last export package
// (`producer_last_package_at`). A healthy export can hide a dead feed; per-source
// freshness needs the deferred `source_monitors` stream.
import { MODULES } from "@/lib/federation";

export const MONITOR_COLLECTION = "MonitoredSources";
export const MONITOR_SUMMARY_COLLECTION = "SourceMonitorSummary";
export const MONITOR_SUMMARY_ID = "source_monitor_summary";
// useEntityData lists at most this many rows; the page warns when the summary
// total is larger instead of truncating silently.
export const MONITOR_LIST_LIMIT = 500;

// Vocabularies mirror src/hub/source_monitor.py (CADENCES / STATUSES).
export const MONITOR_STATUSES = ["active", "partial", "not_active", "manual", "inactive", "unknown"];
export const MONITOR_CADENCES = [
  "realtime", "hourly", "daily", "weekly", "monthly", "quarterly", "yearly",
  "event", "static", "manual", "unknown",
];
export const MONITOR_TIERS = ["T1", "T2", "T3", "T4"];
export const FRESHNESS_STATES = ["Stale", "Due", "Fresh", "Static", "Unknown"];

// Stale first: the operator view leads with what needs attention.
const FRESHNESS_RANK = { Stale: 0, Due: 1, Unknown: 2, Fresh: 3, Static: 4 };

// producer program_id (repo name) -> hub page path, from the module registry.
export const PRODUCER_PAGES = Object.fromEntries(MODULES.map((m) => [m.repo_name, m.path]));
export const MONITOR_PRODUCERS = Object.keys(PRODUCER_PAGES).sort();

export function monitorPath(monitorId) {
  return `/source-monitor/${encodeURIComponent(monitorId)}`;
}

function packageTime(row) {
  const at = row?.producer_last_package_at ? Date.parse(row.producer_last_package_at) : NaN;
  return Number.isFinite(at) ? at : null;
}

// Fresh: export age within the cadence window. Due: past one window. Stale: past
// two. Static: the source does not recur. Unknown: no export timestamp, or a
// cadence with no window (event-driven, manual, undeclared).
export function freshnessState(row, now = Date.now()) {
  if (row?.cadence === "static") return "Static";
  const window = Number(row?.cadence_window_seconds);
  const at = packageTime(row);
  if (at === null || !(window > 0)) return "Unknown";
  const ageSeconds = (now - at) / 1000;
  if (ageSeconds > 2 * window) return "Stale";
  if (ageSeconds > window) return "Due";
  return "Fresh";
}

export function exportAgeDays(row, now = Date.now()) {
  const at = packageTime(row);
  return at === null ? null : Math.max(0, Math.floor((now - at) / 86400000));
}

// rowMap for EntityLedger: adds the derived, filterable/sortable fields.
export function withFreshness(now = Date.now()) {
  return (row) => {
    const freshness = freshnessState(row, now);
    return {
      ...row,
      freshness,
      freshness_rank: FRESHNESS_RANK[freshness],
      export_age_days: exportAgeDays(row, now),
    };
  };
}

export const formatLabel = (value) => (value ? String(value).replaceAll("_", " ") : "—");
