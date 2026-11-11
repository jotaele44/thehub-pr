// Source Monitor (ADR 0012, ADR 0013): shared constants and freshness logic for
// the read-only MonitoredSources views. Rows come from the `source_monitors`
// federation stream for producers that emit it, and from the hub-side registry
// reader (`hub source-monitor`) for the others; `hub ingest` merges the two.
//
// Freshness uses a source's own last success when its producer reports one
// (last_success_basis RUN_RECEIPT or OUTPUT_DERIVED). Otherwise it falls back to
// the age of the producer's last export package, which is labelled as such: a
// healthy export can hide a dead feed.
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

// Where a source's last-success time comes from, as the producer reports it.
// Rows read by the hub-side registry reader carry no basis: "Registry only".
export const SUCCESS_BASIS_LABELS = {
  RUN_RECEIPT: "Run receipt",
  OUTPUT_DERIVED: "From outputs",
  NOT_RECORDED: "Not recorded",
};
export const REGISTRY_ONLY = "Registry only";
export const SUCCESS_BASES = [...Object.values(SUCCESS_BASIS_LABELS), REGISTRY_ONLY];

export function successBasisLabel(row) {
  return SUCCESS_BASIS_LABELS[row?.last_success_basis] || REGISTRY_ONLY;
}

function parseTime(value) {
  const at = value ? Date.parse(value) : NaN;
  return Number.isFinite(at) ? at : null;
}

// The time freshness is measured from: the source's own last success when the
// producer reports one, else the producer's last export package.
export function freshnessReference(row) {
  const reported = row?.last_success_basis === "RUN_RECEIPT" || row?.last_success_basis === "OUTPUT_DERIVED";
  const success = reported ? parseTime(row?.last_success_at) : null;
  if (success !== null) return { at: success, kind: "last_success" };
  return { at: parseTime(row?.producer_last_package_at), kind: "producer_export" };
}

// Fresh: age within the cadence window. Due: past one window. Stale: past two.
// Static: the source does not recur. Unknown: no reference time, or a cadence with
// no window (event-driven, manual, undeclared).
export function freshnessState(row, now = Date.now()) {
  if (row?.cadence === "static") return "Static";
  const window = Number(row?.cadence_window_seconds);
  const { at } = freshnessReference(row);
  if (at === null || !(window > 0)) return "Unknown";
  const ageSeconds = (now - at) / 1000;
  if (ageSeconds > 2 * window) return "Stale";
  if (ageSeconds > window) return "Due";
  return "Fresh";
}

export function ageDays(row, now = Date.now()) {
  const { at } = freshnessReference(row);
  return at === null ? null : Math.max(0, Math.floor((now - at) / 86400000));
}

// Kept for callers written against the producer-export-only model.
export const exportAgeDays = ageDays;

// rowMap for EntityLedger: adds the derived, filterable/sortable fields.
export function withFreshness(now = Date.now()) {
  return (row) => {
    const freshness = freshnessState(row, now);
    return {
      ...row,
      freshness,
      freshness_rank: FRESHNESS_RANK[freshness],
      freshness_kind: freshnessReference(row).kind,
      age_days: ageDays(row, now),
      success_basis: successBasisLabel(row),
    };
  };
}

export const formatLabel = (value) => (value ? String(value).replaceAll("_", " ") : "—");
