// Shared status-chip color maps for the Federation control plane.
// Each map keys a controlled vocabulary value to tailwind classes
// (background / text / border). Rendered via <StatusChip map={...} value={...} />,
// which resolves classes through chipClass(map, value).

const NEUTRAL = "bg-secondary text-muted-foreground border-border";

// Resolve the chip classes for a value; falls back to a neutral chip so
// unknown / legacy values still render instead of breaking the UI.
export function chipClass(map, value) {
  if (!map || value === undefined || value === null) return NEUTRAL;
  return map[value] || map[String(value)] || NEUTRAL;
}

// --- Shared tone shortcuts -------------------------------------------------
const BLUE = "bg-sky-500/15 text-sky-300 border-sky-500/30";
const GREEN = "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
const AMBER = "bg-amber-500/15 text-amber-300 border-amber-500/30";
const RED = "bg-red-500/15 text-red-300 border-red-500/30";
const VIOLET = "bg-violet-500/15 text-violet-300 border-violet-500/30";
const SLATE = "bg-slate-500/15 text-slate-300 border-slate-500/30";
const TEAL = "bg-teal-500/15 text-teal-300 border-teal-500/30";
const YELLOW = "bg-yellow-500/15 text-yellow-300 border-yellow-500/30";
const ORANGE = "bg-orange-500/15 text-orange-300 border-orange-500/30";

// --- Cases -----------------------------------------------------------------
export const CASE_STATUS = {
  New: BLUE,
  Reviewing: AMBER,
  Corroborated: GREEN,
  Contradicted: RED,
  Archived: SLATE,
};

// --- Evidence / confidence -------------------------------------------------
export const CONFIDENCE = {
  Low: SLATE,
  Medium: AMBER,
  High: GREEN,
  Unknown: NEUTRAL,
};

export const SENSITIVITY = {
  Public: SLATE,
  Internal: AMBER,
  Restricted: RED,
};

export const TIER = {
  T1: GREEN,
  T2: TEAL,
  T3: AMBER,
  T4: SLATE,
};

export const SEVERITY = {
  Low: SLATE,
  Medium: YELLOW,
  High: ORANGE,
  Critical: RED,
};

export const PRIORITY = {
  Low: SLATE,
  Medium: BLUE,
  High: ORANGE,
  Critical: RED,
};

// --- Review / verification -------------------------------------------------
export const REVIEW_STATUS = {
  Proposed: BLUE,
  New: BLUE,
  Reviewing: AMBER,
  PendingReview: AMBER,
  Accepted: GREEN,
  Correlated: GREEN,
  Verified: GREEN,
  Disputed: ORANGE,
  Inconclusive: YELLOW,
  Rejected: RED,
  RuledOut: RED,
  Archived: SLATE,
  Low: SLATE,
  Medium: AMBER,
  High: GREEN,
  Unknown: NEUTRAL,
};

export const VERIFICATION = {
  Unreviewed: SLATE,
  Verified: GREEN,
  Disputed: AMBER,
  Rejected: RED,
};

// --- Generic / module ledgers ----------------------------------------------
export const GENERIC_STATUS = {
  New: BLUE,
  Draft: SLATE,
  Proposed: BLUE,
  Reviewing: AMBER,
  Active: GREEN,
  Correlated: GREEN,
  Accepted: GREEN,
  Verified: GREEN,
  Resolved: GREEN,
  Monitored: TEAL,
  Public: SLATE,
  Internal: AMBER,
  Restricted: RED,
  RuledOut: RED,
  Rejected: RED,
  Inactive: SLATE,
  Archived: SLATE,
};

export const DICTIONARY_STATUS = {
  Proposed: BLUE,
  Approved: GREEN,
  Deprecated: SLATE,
};

// --- Governance / control plane ---------------------------------------------
export const PROGRAM_STATUS = {
  Planned: SLATE,
  Active: GREEN,
  Paused: AMBER,
  Archived: SLATE,
};

export const FEDERATION_STATUS = {
  Draft: SLATE,
  Reviewing: AMBER,
  Stable: GREEN,
  NeedsRevision: ORANGE,
  Deprecated: SLATE,
};

export const GITHUB_STATUS = {
  NotConnected: SLATE,
  Blocked: RED,
  Ready: BLUE,
  Connected: GREEN,
};

export const INTEGRATION_STATUS = {
  NotConnected: SLATE,
  Blocked: RED,
  Ready: BLUE,
  Connected: GREEN,
  Error: RED,
};

export const GATE_STATUS = {
  NotStarted: SLATE,
  InProgress: BLUE,
  Passed: GREEN,
  Failed: RED,
  Blocked: AMBER,
};

// --- Task control plane ------------------------------------------------------
export const TASK_LIFECYCLE = {
  Backlog: SLATE,
  Ready: BLUE,
  InProgress: VIOLET,
  Review: AMBER,
  Blocked: RED,
  Done: GREEN,
  Deferred: NEUTRAL,
};

export const GAP_CHIP = {
  "Program Gap": RED,
  "Linkage Gap": AMBER,
  "Due Date Gap": YELLOW,
  "Assignee Gap": ORANGE,
  "Sensitivity Gap": VIOLET,
};
