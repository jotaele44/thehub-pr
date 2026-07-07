// Normalization + derivation helpers for the Federation task control plane.
// Canonical vocabularies mirror the FederationTasks ledger.

export const UNASSIGNED_KEY = "unassigned";

// Canonical program grouping order for the control plane. Real programs use
// prog-* keys (matched against FederationTasks.program_id); the trailing
// bucket collects tasks with a missing or unmappable program.
export const TASK_PROGRAM_ORDER = [
  { key: "prog-hub", label: "Hub / Control Plane", domain: "ControlPlane" },
  { key: "prog-spiderweb", label: "Spiderweb-PR", domain: "NetworkGraph" },
  { key: "prog-ovnis", label: "Ovnis-PR", domain: "UAP" },
  { key: "prog-aguayluz", label: "AguaYLuz-PR", domain: "Infrastructure" },
  { key: "prog-moneysweep", label: "MoneySweep-PR", domain: "Contracts" },
  { key: "prog-skywatcher", label: "Skywatcher-PR", domain: "Airspace" },
  { key: UNASSIGNED_KEY, label: "Unassigned / Needs Mapping", domain: null },
];

export const TASK_STATUS_ORDER = ["Backlog", "Ready", "InProgress", "Review", "Blocked", "Done", "Deferred"];
export const TASK_PRIORITY_ORDER = ["Critical", "High", "Medium", "Low"];
export const TASK_URGENCY_ORDER = [
  "Overdue",
  "Blocked",
  "Due Today",
  "Due This Week",
  "High Priority",
  "Unassigned / Needs Mapping",
  "No Due Date",
];

const OPEN_EXCLUDED = new Set(["Done", "Deferred"]);
const PRIORITY_RANK = { Critical: 0, High: 1, Medium: 2, Low: 3 };

const STATUS_ALIASES = {
  backlog: "Backlog",
  todo: "Backlog",
  planned: "Backlog",
  new: "Backlog",
  open: "Backlog",
  ready: "Ready",
  inprogress: "InProgress",
  "in progress": "InProgress",
  in_progress: "InProgress",
  active: "InProgress",
  doing: "InProgress",
  review: "Review",
  inreview: "Review",
  "in review": "Review",
  needsreview: "Review",
  blocked: "Blocked",
  onhold: "Blocked",
  done: "Done",
  complete: "Done",
  completed: "Done",
  closed: "Done",
  deferred: "Deferred",
  paused: "Deferred",
  cancelled: "Deferred",
  canceled: "Deferred",
};

export function normalizeTaskStatus(status) {
  if (!status) return "Backlog";
  if (TASK_STATUS_ORDER.includes(status)) return status;
  return STATUS_ALIASES[String(status).trim().toLowerCase()] || "Backlog";
}

export function normalizeTaskPriority(priority) {
  if (!priority) return "Medium";
  const p = String(priority).trim().toLowerCase();
  if (p === "critical" || p === "urgent" || p === "p0") return "Critical";
  if (p === "high" || p === "p1") return "High";
  if (p === "low" || p === "p3") return "Low";
  return "Medium";
}

export function normalizeTaskSensitivity(sensitivity) {
  if (!sensitivity) return null;
  const s = String(sensitivity).trim().toLowerCase();
  if (s === "public") return "Public";
  if (s === "restricted" || s === "confidential") return "Restricted";
  if (s === "internal") return "Internal";
  return "Internal";
}

const PROGRAM_BY_KEY = new Map(TASK_PROGRAM_ORDER.map((p) => [p.key, p]));
const UNASSIGNED = PROGRAM_BY_KEY.get(UNASSIGNED_KEY);

// Resolve a task's program group. Direct prog-* keys win; otherwise fall back
// to the Programs ledger (programIndex: Map<program_id, program row>) and try
// to map onto a canonical group by name/domain.
export function resolveTaskProgram(task, programIndex) {
  const pid = task?.program_id;
  if (pid && PROGRAM_BY_KEY.has(pid)) return PROGRAM_BY_KEY.get(pid);
  if (pid && programIndex && typeof programIndex.get === "function" && programIndex.has(pid)) {
    const row = programIndex.get(pid);
    const match = TASK_PROGRAM_ORDER.find(
      (p) => p.key !== UNASSIGNED_KEY && (p.label === row.name || (row.domain && p.domain === row.domain))
    );
    if (match) return match;
    return { key: pid, label: row.name || pid, domain: row.domain || null };
  }
  return UNASSIGNED;
}

export function isTaskOpen(status) {
  return !OPEN_EXCLUDED.has(normalizeTaskStatus(status));
}

const startOfDay = (d) => {
  const c = new Date(d);
  c.setHours(0, 0, 0, 0);
  return c;
};

export function isTaskOverdue(task) {
  if (!task?.due_date || !isTaskOpen(task.status)) return false;
  const due = new Date(task.due_date);
  if (Number.isNaN(due.getTime())) return false;
  return startOfDay(due) < startOfDay(new Date());
}

export function isTaskDueToday(task) {
  if (!task?.due_date || !isTaskOpen(task.status)) return false;
  const due = new Date(task.due_date);
  if (Number.isNaN(due.getTime())) return false;
  return startOfDay(due).getTime() === startOfDay(new Date()).getTime();
}

export function isTaskDueThisWeek(task) {
  if (!task?.due_date || !isTaskOpen(task.status)) return false;
  const due = startOfDay(new Date(task.due_date));
  if (Number.isNaN(due.getTime())) return false;
  const today = startOfDay(new Date());
  const weekOut = new Date(today);
  weekOut.setDate(weekOut.getDate() + 7);
  return due >= today && due <= weekOut;
}

// High/critical priority task overdue or due within 48h → deadline warning.
export function isDeadlineWarning(task) {
  const priority = normalizeTaskPriority(task?.priority);
  if (priority !== "Critical" && priority !== "High") return false;
  if (!isTaskOpen(task?.status)) return false;
  if (isTaskOverdue(task)) return true;
  if (!task?.due_date) return false;
  const due = new Date(task.due_date);
  if (Number.isNaN(due.getTime())) return false;
  return due.getTime() - Date.now() <= 48 * 60 * 60 * 1000;
}

// Linked-record fields → human badge label. First populated linkage wins.
const LINKAGE_FIELDS = [
  ["linked_case_id", "Case"],
  ["linked_source_id", "Source"],
  ["linked_gate_id", "Gate"],
  ["linked_export_id", "Export"],
  ["linked_foia_id", "FOIA"],
  ["linked_integration_id", "Integration"],
  ["linked_contract_id", "Contract"],
  ["linked_vendor_id", "Vendor"],
  ["linked_anomaly_id", "Anomaly"],
  ["linked_asset_id", "Asset"],
  ["linked_risk_id", "Risk"],
  ["linked_airspace_event_id", "Airspace Event"],
  ["linked_correlation_id", "Correlation"],
  ["linked_node_id", "Graph Node"],
  ["linked_edge_id", "Graph Edge"],
  ["linked_pattern_id", "Pattern"],
  ["linked_witness_id", "Witness"],
  ["linked_vector", "Vector"],
];

export function getTaskLinkageBadge(task) {
  for (const [field, label] of LINKAGE_FIELDS) {
    if (task?.[field]) return label;
  }
  return "Unlinked";
}

// Control-plane hygiene gaps for a task (subset of the canonical GAP labels).
export function getTaskGapBadges(task, programIndex) {
  const gaps = [];
  const program = resolveTaskProgram(task, programIndex);
  if (program.key === UNASSIGNED_KEY) gaps.push("Program Gap");
  if (getTaskLinkageBadge(task) === "Unlinked") gaps.push("Linkage Gap");
  if (!task?.due_date && isTaskOpen(task?.status)) gaps.push("Due Date Gap");
  if (!task?.assigned_to && isTaskOpen(task?.status)) gaps.push("Assignee Gap");
  if (!task?.sensitivity) gaps.push("Sensitivity Gap");
  return gaps;
}

// Single urgency bucket per task (first match wins); closed tasks are excluded.
export function getTaskUrgencyBucket(task, programIndex) {
  if (!isTaskOpen(task?.status)) return null;
  if (isTaskOverdue(task)) return "Overdue";
  if (normalizeTaskStatus(task?.status) === "Blocked") return "Blocked";
  if (isTaskDueToday(task)) return "Due Today";
  if (isTaskDueThisWeek(task)) return "Due This Week";
  const priority = normalizeTaskPriority(task?.priority);
  if (priority === "Critical" || priority === "High") return "High Priority";
  if (resolveTaskProgram(task, programIndex).key === UNASSIGNED_KEY) return "Unassigned / Needs Mapping";
  if (!task?.due_date) return "No Due Date";
  return null;
}

// Overdue first, then nearest due date, then priority rank.
export function sortTasksByUrgency(tasks = []) {
  return [...tasks].sort((a, b) => {
    const ao = isTaskOverdue(a) ? 0 : 1;
    const bo = isTaskOverdue(b) ? 0 : 1;
    if (ao !== bo) return ao - bo;
    const ad = a.due_date ? new Date(a.due_date).getTime() : Infinity;
    const bd = b.due_date ? new Date(b.due_date).getTime() : Infinity;
    if (ad !== bd) return ad - bd;
    const ap = PRIORITY_RANK[normalizeTaskPriority(a.priority)] ?? 9;
    const bp = PRIORITY_RANK[normalizeTaskPriority(b.priority)] ?? 9;
    return ap - bp;
  });
}

// Allowed lifecycle transitions from a given (normalized) status.
// Admins may move tasks anywhere; regular users follow the forward flow.
const TRANSITIONS = {
  Backlog: ["Ready", "InProgress", "Deferred"],
  Ready: ["InProgress", "Backlog", "Deferred"],
  InProgress: ["Review", "Blocked", "Done"],
  Review: ["Done", "InProgress", "Blocked"],
  Blocked: ["Ready", "InProgress", "Deferred"],
  Done: ["InProgress"],
  Deferred: ["Backlog", "Ready"],
};

export function getTaskLifecycleOptions(status, role = "user") {
  const current = normalizeTaskStatus(status);
  if (role === "admin") return TASK_STATUS_ORDER.filter((s) => s !== current);
  return TRANSITIONS[current] || [];
}
