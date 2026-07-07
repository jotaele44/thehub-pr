// Live dashboard refresh + staleness configuration (single source of truth).
// Tune these to change how aggressively feeds poll and when they warn "stale".

// How often live dashboards re-poll feed data.
export const LIVE_INTERVAL_MS = 30000; // 30s

// Data / a source is considered stale after ~3 missed intervals,
// so the "Live" indicator never lies after a failed or skipped refresh.
export const STALE_AFTER_MS = 90000; // 90s