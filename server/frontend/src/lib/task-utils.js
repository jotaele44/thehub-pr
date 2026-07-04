export const CONTROL_PROGRAM_ID = 'prog-control';
export const UNASSIGNED_KEY = '__unassigned__';
export const TASK_PROGRAM_ORDER = [
  { key: 'prog-control', label: 'INTSYS-PR', domain: 'ControlPlane' },
  { key: 'prog-spiderweb', label: 'Spiderweb-PR', domain: 'NetworkGraph' },
  { key: 'prog-ovnis', label: 'Ovnis-PR', domain: 'UAP' },
  { key: 'prog-aguayluz', label: 'AguaYLuz-PR', domain: 'Infrastructure' },
  { key: 'prog-moneysweep', label: 'MoneySweep-PR', domain: 'Contracts' },
  { key: 'prog-skywatcher', label: 'Skywatcher-PR', domain: 'Airspace' },
];
export const TASK_STATUS_ORDER = ['Backlog', 'Ready', 'InProgress', 'Blocked', 'Review', 'Done', 'Deferred'];
export const TASK_PRIORITY_ORDER = ['Critical', 'High', 'Medium', 'Low'];
export const TASK_URGENCY_ORDER = ['overdue', 'due_today', 'due_this_week', 'blocked', 'high_priority', 'normal'];

const STATUS_ALIASES = { backlog: 'Backlog', queued: 'Backlog', ready: 'Ready', todo: 'Ready', inprogress: 'InProgress', in_progress: 'InProgress', 'in progress': 'InProgress', active: 'InProgress', blocked: 'Blocked', review: 'Review', reviewing: 'Review', done: 'Done', complete: 'Done', completed: 'Done', closed: 'Done', deferred: 'Deferred' };
const PRIORITY_ALIASES = { critical: 'Critical', crit: 'Critical', high: 'High', medium: 'Medium', med: 'Medium', normal: 'Medium', low: 'Low' };
const SENSITIVITY_ALIASES = { public: 'Public', internal: 'Internal', restricted: 'Restricted' };

export function normalizeTaskStatus(value) {
  if (!value) return 'Backlog';
  const k = String(value).trim().toLowerCase().replace(/\s+/g, ' ');
  return STATUS_ALIASES[k] || STATUS_ALIASES[k.replace(/ /g, '_')] || 'Backlog';
}
export function normalizeTaskPriority(value) {
  if (!value) return 'Medium';
  return PRIORITY_ALIASES[String(value).trim().toLowerCase()] || 'Medium';
}
export function normalizeTaskSensitivity(value) {
  if (!value) return null;
  return SENSITIVITY_ALIASES[String(value).trim().toLowerCase()] || null;
}
export function resolveTaskProgram(task, programIndex = new Map()) {
  const pid = task?.program_id;
  const canonical = TASK_PROGRAM_ORDER.find((p) => p.key === pid);
  if (canonical) return canonical;
  const prog = pid && programIndex.get(pid);
  if (prog?.name) {
    const byName = TASK_PROGRAM_ORDER.find((p) => p.label === prog.name);
    if (byName) return byName;
  }
  return { key: UNASSIGNED_KEY, label: 'Unassigned / Needs Program Mapping', domain: 'ControlPlane' };
}
function parseDue(due) { if (!due) return null; const d = new Date(due); return Number.isNaN(d.getTime()) ? null : d; }
function startOfDay(d) { const x = new Date(d); x.setHours(0, 0, 0, 0); return x; }
export function isTaskOpen(status) { return ['Backlog', 'Ready', 'InProgress', 'Blocked', 'Review'].includes(normalizeTaskStatus(status)); }
export function isTaskOverdue(task) { const d = parseDue(task?.due_date); return d && normalizeTaskStatus(task.status) !== 'Done' && startOfDay(d) < startOfDay(new Date()); }
export function isTaskDueToday(task) { const d = parseDue(task?.due_date); return !!d && startOfDay(d).getTime() === startOfDay(new Date()).getTime(); }
export function isTaskDueThisWeek(task) { const d = parseDue(task?.due_date); if (!d) return false; const today = startOfDay(new Date()); const end = new Date(today); end.setDate(end.getDate() + 7); const due = startOfDay(d); return due >= today && due <= end; }
export function isDeadlineWarning(task) { const pr = normalizeTaskPriority(task?.priority); return (pr === 'Critical' || pr === 'High') && normalizeTaskStatus(task?.status) !== 'Done' && !!parseDue(task?.due_date); }
export function getTaskUrgencyBucket(task) { if (isTaskOverdue(task)) return 'overdue'; if (isTaskDueToday(task)) return 'due_today'; if (normalizeTaskStatus(task?.status) === 'Blocked') return 'blocked'; if (isTaskDueThisWeek(task)) return 'due_this_week'; if (['Critical', 'High'].includes(normalizeTaskPriority(task?.priority))) return 'high_priority'; return 'normal'; }
const LINKAGE_FIELDS = ['linked_case_id','linked_source_id','linked_gate_id','linked_vector','linked_export_id','linked_foia_id','linked_integration_id','linked_contract_id','linked_vendor_id','linked_anomaly_id','linked_asset_id','linked_risk_id','linked_airspace_event_id','linked_correlation_id','linked_node_id','linked_edge_id','linked_pattern_id','linked_witness_id'];
export function getTaskLinkageBadge(task) { const hit = LINKAGE_FIELDS.find((f) => task?.[f]); return hit ? hit.replace(/^linked_/, '').replace(/_id$/, '').replace(/_/g, '-') : (task?.program_id ? 'Program Task' : 'Unlinked'); }
export function getTaskGapBadges(task, programIndex = new Map()) { const gaps = []; if (!task?.program_id || !programIndex.has(task.program_id)) gaps.push('Program Gap'); if (!task?.due_date) gaps.push('Missing Due Date'); if (getTaskLinkageBadge(task) === 'Unlinked') gaps.push('Unlinked'); return gaps; }
const priorityRank = { Critical: 0, High: 1, Medium: 2, Low: 3 };
export function sortTasksByUrgency(tasks) { return [...tasks].sort((a, b) => (TASK_URGENCY_ORDER.indexOf(getTaskUrgencyBucket(a)) - TASK_URGENCY_ORDER.indexOf(getTaskUrgencyBucket(b))) || (priorityRank[normalizeTaskPriority(a.priority)] - priorityRank[normalizeTaskPriority(b.priority)]) || String(a.title || '').localeCompare(String(b.title || ''))); }
export function getTaskLifecycleOptions(status, role = 'user') { const s = normalizeTaskStatus(status); const transitions = { Backlog: ['Ready', 'Deferred'], Ready: ['InProgress', 'Blocked'], InProgress: ['Review', 'Blocked', 'Deferred'], Blocked: ['Ready', 'Deferred'], Review: ['Done', 'InProgress'], Done: role === 'admin' ? ['InProgress'] : [], Deferred: role === 'admin' || role === 'analyst' ? ['Ready'] : [] }; return transitions[s] || []; }
