// Federation task control plane utilities.
// Canonical program identity, normalization, urgency, linkage, and gap logic.
// Uses FederationTasks + Programs only. No new entities.

// ── Canonical program identity ──────────────────────────────────────────────
export const CONTROL_PROGRAM_ID = "prog-control";
export const UNASSIGNED_KEY = "__unassigned__";
export const UNASSIGNED_LABEL = "Unassigned / Needs Program Mapping";

// Fixed canonical order (program_id -> canonical label)
export const TASK_PROGRAM_ORDER = [
  { key: "prog-control", label: "INTSYS-PR", domain: "ControlPlane" },
  { key: "prog-spiderweb", label: "Spiderweb-PR", domain: "NetworkGraph" },
  { key: "prog-ovnis", label: "Ovnis-PR", domain: "UAP" },
  { key: "prog-aguayluz", label: "AguaYLuz-PR", domain: "Infrastructure" },
  { key: "prog-moneysweep", label: "MoneySweep-PR", domain: "Contracts" },
  { key: "prog-skywatcher", label: "Skywatcher-PR", domain: "Airspace" },
  { key: UNASSIGNED_KEY, label: UNASSIGNED_LABEL, domain: "ControlPlane" },
];

const CANONICAL_LABELS = new Set(TASK_PROGRAM_ORDER.map((p) => p.label));

// Resolve a task to its canonical { key, label, domain } using the Programs ledger.
// programIndex: Map(program_id -> program record).
export function resolveTaskProgram(task, programIndex) {
  const pid = task?.program_id;
  if (pid && programIndex.has(pid)) {
    const prog = programIndex.get(pid);
    const canonical = TASK_PROGRAM_ORDER.find((p) => p.key === pid);
    // Only render canonical labels; fall back to ledger name if canonical, else Unassigned.
    if (canonical) return { key: canonical.key, label: canonical.label, domain: canonical.domain };
    if (prog?.name && CANONICAL_LABELS.has(prog.name)) {
      const match = TASK_PROGRAM_ORDER.find((p) => p.label === prog.name);
      return { key: match.key, label: match.label, domain: match.domain };
    }
  }
  return { key: UNASSIGNED_KEY, label: UNASSIGNED_LABEL, domain: "ControlPlane" };
}

// ── Lifecycle status ────────────────────────────────────────────────────────
export const TASK_STATUS_ORDER = ["Backlog", "Ready", "InProgress", "Blocked", "Review", "Done", "Deferred"];

const STATUS_ALIASES = {
  backlog: "Backlog",
  queued: "Backlog",
  ready: "Ready",
  todo: "Ready",
  inprogress: "InProgress",
  in_progress: "InProgress",
  "in progress": "InProgress",
  active: "InProgress",
  blocked: "Blocked",
  review: "Review",
  reviewing: "Review",
  done: "Done",
  complete: "Done",
  completed: "Done",
  closed: "Done",
  deferred: "Deferred",
};

export function normalizeTaskStatus(value) {
  if (!value) return "Backlog";
  const k = String(value).trim().toLowerCase().replace(/\s+/g, " ");
  return STATUS_ALIASES[k] || STATUS_ALIASES[k.replace(/ /g, "_")] || "Backlog";
}

// ── Priority ────────────────────────────────────────────────────────────────
export const TASK_PRIORITY_ORDER = ["Critical", "High", "Medium", "Low"];

const PRIORITY_ALIASES = {
  critical: "Critical", crit: "Critical",
  high: "High",
  medium: "Medium", med: "Medium", normal: "Medium",
  low: "Low",
};

export function normalizeTaskPriority(value) {
  if (!value) return "Medium";
  const k = String(value).trim().toLowerCase();
  return PRIORITY_ALIASES[k] || "Medium";
}

const PRIORITY_RANK = { Critical: 0, High: 1, Medium: 2, Low: 3 };

// ── Sensitivity ─────────────────────────────────────────────────────────────
const SENSITIVITY_ALIASES = {
  public: "Public",
  internal: "Internal",
  restricted: "Restricted",
};

export function normalizeTaskSensitivity(value) {
  if (!value) return null;
  const k = String(value).trim().toLowerCase();
  return SENSITIVITY_ALIASES[k] || null;
}

// ── Date helpers ────────────────────────────────────────────────────────────
function parseDue(due) {
  if (!due) return null;
  const d = new Date(due);
  return isNaN(d.getTime()) ? null : d;
}

function startOfDay(d) {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

const OPEN_STATUSES = new Set(["Backlog", "Ready", "InProgress", "Blocked", "Review"]);

export function isTaskOpen(status) {
  return OPEN_STATUSES.has(normalizeTaskStatus(status));
}

export function isTaskOverdue(task) {
  if (normalizeTaskStatus(task.status) === "Done") return false;
  const d = parseDue(task.due_date);
  if (!d) return false;
  return startOfDay(d) < startOfDay(new Date());
}

export function isTaskDueToday(task) {
  const d = parseDue(task.due_date);
  if (!d) return false;
  return startOfDay(d).getTime() === startOfDay(new Date()).getTime();
}

export function isTaskDueThisWeek(task) {
  const d = parseDue(task.due_date);
  if (!d) return false;
  const today = startOfDay(new Date());
  const end = new Date(today);
  end.setDate(end.getDate() + 7);
  const due = startOfDay(d);
  return due >= today && due <= end;
}

// High priority due within next 48 hours and not done — deadline warning.
export function isDeadlineWarning(task) {
  const pr = normalizeTaskPriority(task.priority);
  if (pr !== "Critical" && pr !== "High") return false;
  if (normalizeTaskStatus(task.status) === "Done") return false;
  const d = parseDue(task.due_date);
  if (!d) return false;
  const now = new Date();
  const limit = new Date(now.getTime() + 48 * 60 * 60 * 1000);
  // Include overdue high-priority within the warning band too.
  return d <= limit;
}

// ── Lifecycle transitions (UI-level) ─────────────────────────────────────────
const TRANSITIONS = {
  Backlog: ["Ready", "Deferred"],
  Ready: ["InProgress", "Blocked"],
  InProgress: ["Review", "Blocked", "Deferred"],
  Blocked: ["Ready", "Deferred"],
  Review: ["Done", "InProgress"],
  Done: ["InProgress"], // Reopen, admin-gated
  Deferred: ["Ready"], // admin/analyst-gated
};

// role: "admin" | "analyst" | "reviewer" | "user"
export function getTaskLifecycleOptions(status, role = "user") {
  const s = normalizeTaskStatus(status);
  let opts = TRANSITIONS[s] || [];
  if (s === "Done" && role !== "admin") opts = [];
  if (s === "Deferred" && !(role === "admin" || role === "analyst")) opts = [];
  return opts;
}

// ── Linkage badges ──────────────────────────────────────────────────────────
// Ordered: first matching field wins for the primary badge; all matches returned too.
const LINKAGE_FIELDS = [
  { field: "linked_case_id", label: "Case-linked" },
  { field: "linked_source_id", label: "Source-linked" },
  { field: "linked_gate_id", label: "Gate-linked" },
  { field: "linked_vector", label: "Vector-linked" },
  { field: "linked_export_id", label: "Export-linked" },
  { field: "linked_foia_id", label: "FOIA-linked" },
  { field: "linked_integration_id", label: "Integration-linked" },
  { field: "linked_contract_id", label: "Contract-linked" },
  { field: "linked_vendor_id", label: "Vendor-linked" },
  { field: "linked_anomaly_id", label: "AnomalyFlag-linked" },
  { field: "linked_asset_id", label: "Infrastructure-linked" },
  { field: "linked_risk_id", label: "ContinuityRisk-linked" },
  { field: "linked_airspace_event_id", label: "AirspaceEvent-linked" },
  { field: "linked_correlation_id", label: "CorrelationReview-linked" },
  { field: "linked_node_id", label: "GraphNode-linked" },
  { field: "linked_edge_id", label: "GraphEdge-linked" },
  { field: "linked_pattern_id", label: "PatternObservation-linked" },
  { field: "linked_witness_id", label: "WitnessReport-linked" },
];

function hasValue(v) {
  return v !== undefined && v !== null && String(v).trim() !== "";
}

// Primary linkage badge for compact display.
export function getTaskLinkageBadge(task) {
  for (const l of LINKAGE_FIELDS) {
    if (hasValue(task[l.field])) return l.label;
  }
  if (hasValue(task.program_id)) return "Program Task";
  return "Unlinked";
}

// All linkage references present (for table / detail).
export function getTaskLinkages(task) {
  const out = LINKAGE_FIELDS.filter((l) => hasValue(task[l.field])).map((l) => ({ label: l.label, value: task[l.field] }));
  return out;
}

// ── Gap detection ───────────────────────────────────────────────────────────
export function getTaskGapBadges(task, programIndex) {
  const gaps = [];
  const pid = task.program_id;
  if (!pid || !programIndex.has(pid)) gaps.push("Program Gap");
  const hasLink = LINKAGE_FIELDS.some((l) => hasValue(task[l.field]));
  if (!hasLink) gaps.push("Linkage Gap");
  if (!hasValue(task.due_date)) gaps.push("Due Date Gap");
  if (!hasValue(task.assigned_to)) gaps.push("Assignee Gap");
  if (!hasValue(task.sensitivity)) gaps.push("Sensitivity Gap");
  return gaps;
}

// ── Urgency buckets ─────────────────────────────────────────────────────────
export const TASK_URGENCY_ORDER = [
  "Overdue",
  "Blocked",
  "Due Today",
  "Due This Week",
  "High Priority",
  "Unassigned / Needs Mapping",
  "No Due Date",
];

// Returns the single primary urgency bucket for a task.
export function getTaskUrgencyBucket(task, programIndex) {
  const status = normalizeTaskStatus(task.status);
  if (status === "Done" || status === "Deferred") return null;
  if (isTaskOverdue(task)) return "Overdue";
  if (status === "Blocked") return "Blocked";
  if (isTaskDueToday(task)) return "Due Today";
  if (isTaskDueThisWeek(task)) return "Due This Week";
  const pr = normalizeTaskPriority(task.priority);
  if (pr === "Critical" || pr === "High") return "High Priority";
  if (!task.program_id || !programIndex.has(task.program_id)) return "Unassigned / Needs Mapping";
  if (!task.due_date) return "No Due Date";
  return "No Due Date";
}

// ── Sorting ─────────────────────────────────────────────────────────────────
export function sortTasksByUrgency(tasks) {
  const copy = [...tasks];
  copy.sort((a, b) => {
    const ao = isTaskOverdue(a) ? 0 : 1;
    const bo = isTaskOverdue(b) ? 0 : 1;
    if (ao !== bo) return ao - bo;
    const ad = parseDue(a.due_date);
    const bd = parseDue(b.due_date);
    if (ad && bd && ad.getTime() !== bd.getTime()) return ad - bd;
    if (ad && !bd) return -1;
    if (!ad && bd) return 1;
    return PRIORITY_RANK[normalizeTaskPriority(a.priority)] - PRIORITY_RANK[normalizeTaskPriority(b.priority)];
  });
  return copy;
}

export function sortTasksByProgramOrder(tasks, programIndex) {
  const idx = Object.fromEntries(TASK_PROGRAM_ORDER.map((p, i) => [p.key, i]));
  const copy = [...tasks];
  copy.sort((a, b) => {
    const ak = resolveTaskProgram(a, programIndex).key;
    const bk = resolveTaskProgram(b, programIndex).key;
    return (idx[ak] ?? 99) - (idx[bk] ?? 99);
  });
  return copy;
}