import { useMemo } from "react";
import { useEntityData } from "@/hooks/useEntityData";
import {
  TASK_PROGRAM_ORDER, TASK_URGENCY_ORDER, TASK_STATUS_ORDER, UNASSIGNED_KEY,
  normalizeTaskStatus, normalizeTaskPriority, normalizeTaskSensitivity,
  resolveTaskProgram, getTaskUrgencyBucket, getTaskGapBadges,
  isTaskOpen, isTaskOverdue, isTaskDueThisWeek, isTaskDueToday, isDeadlineWarning,
  getTaskLinkageBadge, sortTasksByUrgency,
} from "@/lib/task-utils";

// Central data + processing layer for the Federation task control plane.
// filters: { search, program, status, priority, sensitivity, assignee, due, linkage, gap }
export function useTaskControlPlane(filters = {}) {
  const { rows: rawTasks, isLoading: loadingTasks, create, update, saving } = useEntityData("FederationTasks");
  const { rows: programs, isLoading: loadingPrograms } = useEntityData("Programs");

  const programIndex = useMemo(
    () => new Map(programs.map((p) => [p.program_id, p])),
    [programs]
  );

  // Decorate each task with normalized + resolved values once.
  const tasks = useMemo(() => rawTasks.map((t) => {
    const program = resolveTaskProgram(t, programIndex);
    return {
      ...t,
      _status: normalizeTaskStatus(t.status),
      _priority: normalizeTaskPriority(t.priority),
      _sensitivity: normalizeTaskSensitivity(t.sensitivity),
      _programKey: program.key,
      _programLabel: program.label,
      _programDomain: program.domain,
      _linkage: getTaskLinkageBadge(t),
      _gaps: getTaskGapBadges(t, programIndex),
      _overdue: isTaskOverdue(t),
      _dueThisWeek: isTaskDueThisWeek(t),
      _dueToday: isTaskDueToday(t),
      _open: isTaskOpen(t.status),
      _warning: isDeadlineWarning(t),
    };
  }), [rawTasks, programIndex]);

  // Apply global filters BEFORE grouping.
  const filtered = useMemo(() => {
    const q = (filters.search || "").trim().toLowerCase();
    return tasks.filter((t) => {
      if (q) {
        const hay = `${t.title || ""} ${t.task_id || ""} ${t.assigned_to || ""} ${t.summary || ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      if (filters.program && filters.program !== "all" && t._programKey !== filters.program) return false;
      if (filters.status && filters.status !== "all" && t._status !== filters.status) return false;
      if (filters.priority && filters.priority !== "all" && t._priority !== filters.priority) return false;
      if (filters.sensitivity && filters.sensitivity !== "all" && t._sensitivity !== filters.sensitivity) return false;
      if (filters.assignee && filters.assignee !== "all" && (t.assigned_to || "—") !== filters.assignee) return false;
      if (filters.linkage && filters.linkage !== "all" && t._linkage !== filters.linkage) return false;
      if (filters.gap && filters.gap !== "all" && !t._gaps.includes(filters.gap)) return false;
      if (filters.due && filters.due !== "all") {
        if (filters.due === "Overdue" && !t._overdue) return false;
        if (filters.due === "Due Today" && !t._dueToday) return false;
        if (filters.due === "Due This Week" && !t._dueThisWeek) return false;
        if (filters.due === "No Due Date" && t.due_date) return false;
      }
      return true;
    });
  }, [tasks, filters]);

  // Grouped by program (fixed canonical order).
  const grouped = useMemo(() => {
    return TASK_PROGRAM_ORDER.map((p) => {
      const groupTasks = sortTasksByUrgency(filtered.filter((t) => t._programKey === p.key));
      return {
        ...p,
        tasks: groupTasks,
        metrics: computeMetrics(groupTasks),
      };
    });
  }, [filtered]);

  // Urgency buckets.
  const urgency = useMemo(() => {
    const buckets = Object.fromEntries(TASK_URGENCY_ORDER.map((b) => [b, []]));
    filtered.forEach((t) => {
      const b = getTaskUrgencyBucket(t, programIndex);
      if (b && buckets[b]) buckets[b].push(t);
    });
    return TASK_URGENCY_ORDER.map((label) => ({ label, tasks: sortTasksByUrgency(buckets[label]) }));
  }, [filtered, programIndex]);

  // Lifecycle board columns.
  const board = useMemo(() => {
    return TASK_STATUS_ORDER.map((status) => ({
      status,
      tasks: filtered.filter((t) => t._status === status),
    }));
  }, [filtered]);

  // Global rollup metrics (over filtered set).
  const rollups = useMemo(() => {
    const byProgram = TASK_PROGRAM_ORDER.map((p) => ({
      key: p.key, label: p.label, domain: p.domain,
      open: filtered.filter((t) => t._programKey === p.key && t._open).length,
    }));
    const linkageCounts = {};
    filtered.forEach((t) => { linkageCounts[t._linkage] = (linkageCounts[t._linkage] || 0) + 1; });
    const recent = [...filtered].sort((a, b) =>
      new Date(b.updated_date || b.created_date || 0) - new Date(a.updated_date || a.created_date || 0)
    ).slice(0, 6);
    return {
      ...computeMetrics(filtered),
      byProgram,
      linkageCounts,
      recent,
      unassigned: filtered.filter((t) => t._programKey === UNASSIGNED_KEY).length,
      warnings: filtered.filter((t) => t._warning),
    };
  }, [filtered]);

  return {
    isLoading: loadingTasks || loadingPrograms,
    programs, programIndex,
    tasks: filtered,
    grouped, urgency, board, rollups,
    create, update, saving,
  };
}

function computeMetrics(tasks) {
  return {
    total: tasks.length,
    open: tasks.filter((t) => t._open).length,
    overdue: tasks.filter((t) => t._overdue).length,
    blocked: tasks.filter((t) => t._status === "Blocked").length,
    high: tasks.filter((t) => t._priority === "Critical" || t._priority === "High").length,
    dueThisWeek: tasks.filter((t) => t._dueThisWeek).length,
    gaps: tasks.filter((t) => t._gaps.length > 0).length,
  };
}

// Module-scoped metrics for child dashboards.
export function useModuleTaskMetrics(programKey) {
  const { tasks } = useTaskControlPlane();
  return useMemo(() => {
    const scoped = tasks.filter((t) => t._programKey === programKey);
    return {
      ...computeMetrics(scoped),
      recent: [...scoped].sort((a, b) =>
        new Date(b.updated_date || b.created_date || 0) - new Date(a.updated_date || a.created_date || 0)
      ).slice(0, 5),
    };
  }, [tasks, programKey]);
}