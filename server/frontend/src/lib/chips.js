// Centralized status chip color maps. Neutral analytical language only.

const C = {
  gray: "bg-slate-500/15 text-slate-300 border-slate-500/30",
  blue: "bg-blue-500/15 text-blue-300 border-blue-500/30",
  green: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  yellow: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30",
  amber: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  red: "bg-red-500/15 text-red-300 border-red-500/30",
  violet: "bg-violet-500/15 text-violet-300 border-violet-500/30",
  teal: "bg-teal-500/15 text-teal-300 border-teal-500/30",
};

export const CONFIDENCE = { Low: C.yellow, Medium: C.blue, High: C.green };

export const SENSITIVITY = { Public: C.gray, Internal: C.amber, Restricted: C.red };

export const VERIFICATION = {
  Unreviewed: C.gray, Verified: C.green, Disputed: C.amber, Rejected: C.red,
};

export const GATE_STATUS = {
  NotStarted: C.gray, InProgress: C.blue, Passed: C.green, Failed: C.red, Blocked: C.red,
};

export const CASE_STATUS = {
  New: C.gray, Reviewing: C.blue, Corroborated: C.green, Contradicted: C.amber, Archived: C.gray,
};

export const TASK_STATUS = {
  Queued: C.gray, InProgress: C.blue, Blocked: C.red, Complete: C.green, Deferred: C.gray,
};

// Canonical lifecycle status chip map (task control plane).
export const TASK_LIFECYCLE = {
  Backlog: C.gray, Ready: C.teal, InProgress: C.blue, Blocked: C.red,
  Review: C.violet, Done: C.green, Deferred: C.gray,
};

export const PRIORITY = { Low: C.gray, Medium: C.blue, High: C.amber, Critical: C.red };

// Gap warning chips — neutral amber/yellow tone.
export const GAP_CHIP = {
  "Program Gap": C.amber, "Linkage Gap": C.yellow, "Due Date Gap": C.yellow,
  "Assignee Gap": C.yellow, "Sensitivity Gap": C.amber,
};

export const PROGRAM_STATUS = { Planned: C.gray, Active: C.green, Paused: C.amber, Archived: C.gray };

export const GITHUB_STATUS = {
  NotConnected: C.gray, Blocked: C.red, Ready: C.green, Connected: C.blue,
};

export const FEDERATION_STATUS = {
  Draft: C.gray, Reviewing: C.blue, Stable: C.green, NeedsRevision: C.amber,
};

export const INTEGRATION_STATUS = {
  NotConnected: C.gray, Blocked: C.red, Ready: C.green, Connected: C.blue, Error: C.red,
};

export const SEVERITY = { Low: C.gray, Medium: C.blue, High: C.amber, Critical: C.red };

export const TIER = { T1: C.green, T2: C.teal, T3: C.blue, T4: C.gray };

export const REVIEW_STATUS = {
  Proposed: C.gray, Reviewing: C.blue, Accepted: C.green, Disputed: C.amber,
  Rejected: C.red, FalsePositive: C.violet, Inconclusive: C.amber,
  Unreviewed: C.gray, Reviewed: C.green, NeedsFollowup: C.amber,
};

export const DICTIONARY_STATUS = { Proposed: C.gray, Approved: C.green, Deprecated: C.amber };

export const GENERIC_STATUS = {
  New: C.gray, Reviewing: C.blue, Mitigated: C.green, Archived: C.gray,
  Correlated: C.green, RuledOut: C.amber, Flagged: C.amber, Cleared: C.green,
  Active: C.green, Inactive: C.gray, Unknown: C.gray, UnderReview: C.blue,
  Sanitized: C.green, Excluded: C.gray,
};

export const chipClass = (map, value) => map[value] || C.gray;