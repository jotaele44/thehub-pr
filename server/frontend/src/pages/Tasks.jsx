import React, { useState, useMemo, useEffect } from "react";
import { federation } from "@/api/federationClient";
import { useSearchParams } from "react-router-dom";
import { useTaskControlPlane } from "@/hooks/useTaskControlPlane";
import PageHeader from "@/components/shared/PageHeader";
import RecordSheet from "@/components/shared/RecordSheet";
import { Button } from "@/components/ui/button";
import { ListChecks, Plus, Info } from "lucide-react";
import {
  TASK_PROGRAM_ORDER, TASK_STATUS_ORDER, TASK_PRIORITY_ORDER,
} from "@/lib/task-utils";
import ViewToggle from "@/components/tasks/ViewToggle";
import TaskFilterBar from "@/components/tasks/TaskFilterBar";
import DeadlineWarningBanner from "@/components/tasks/DeadlineWarningBanner";
import GroupedView from "@/components/tasks/views/GroupedView";
import UrgencyView from "@/components/tasks/views/UrgencyView";
import FlatTableView from "@/components/tasks/views/FlatTableView";
import LifecycleBoardView from "@/components/tasks/views/LifecycleBoardView";

const TYPES = ["Review", "SourceCheck", "DataEntry", "FOIA", "GIS", "Export", "Validation", "GitHub", "Other"];
const SENSITIVITIES = ["Public", "Internal", "Restricted"];
const GAP_TYPES = ["Program Gap", "Linkage Gap", "Due Date Gap", "Assignee Gap", "Sensitivity Gap"];

export default function Tasks() {
  const [searchParams] = useSearchParams();
  const [view, setView] = useState("grouped");
  const [filters, setFilters] = useState({});
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [role, setRole] = useState("user");

  useEffect(() => {
    federation.auth.me().then((u) => setRole(u?.role || "user")).catch(() => setRole("user"));
  }, []);

  // Honor ?program= deep links from dashboards.
  useEffect(() => {
    const p = searchParams.get("program");
    if (p) setFilters((f) => ({ ...f, program: p }));
  }, [searchParams]);

  const { grouped, urgency, board, tasks, rollups, programIndex, create, update, saving } = useTaskControlPlane(filters);

  const assignees = useMemo(() => {
    const set = new Set();
    rollups && tasks.forEach((t) => t.assigned_to && set.add(t.assigned_to));
    return Array.from(set).sort();
  }, [tasks, rollups]);

  const allTasks = useMemo(() => grouped.flatMap((g) => g.tasks), [grouped]);

  const filterDefs = [
    { key: "program", label: "Program", options: TASK_PROGRAM_ORDER.map((p) => ({ value: p.key, label: p.label })) },
    { key: "status", label: "Status", options: TASK_STATUS_ORDER.map((s) => ({ value: s, label: s })) },
    { key: "priority", label: "Priority", options: TASK_PRIORITY_ORDER.map((s) => ({ value: s, label: s })) },
    { key: "sensitivity", label: "Sensitivity", options: SENSITIVITIES.map((s) => ({ value: s, label: s })) },
    { key: "assignee", label: "Assignee", options: assignees.map((a) => ({ value: a, label: a })) },
    { key: "due", label: "Due", options: ["Overdue", "Due Today", "Due This Week", "No Due Date"].map((s) => ({ value: s, label: s })) },
    { key: "gap", label: "Gap", options: GAP_TYPES.map((s) => ({ value: s, label: s })) },
  ];

  const setFilter = (key, value) => setFilters((f) => ({ ...f, [key]: value }));
  const clearFilters = () => setFilters({});
  const hasActive = Object.values(filters).some((v) => v && v !== "all" && v !== "");

  const FIELDS = [
    { key: "task_id", label: "Task ID", required: true, placeholder: "task-001" },
    { key: "program_id", label: "Program", type: "select", options: TASK_PROGRAM_ORDER.filter((p) => p.key.startsWith("prog")).map((p) => p.key), required: true },
    { key: "title", label: "Title", required: true, full: true },
    { key: "task_type", label: "Type", type: "select", options: TYPES },
    { key: "priority", label: "Priority", type: "select", options: ["Low", "Medium", "High", "Critical"], required: true },
    { key: "status", label: "Status", type: "select", options: TASK_STATUS_ORDER, required: true },
    { key: "sensitivity", label: "Sensitivity", type: "select", options: SENSITIVITIES },
    { key: "assigned_to", label: "Assigned To" },
    { key: "due_date", label: "Due Date", type: "date" },
    { key: "summary", label: "Summary", type: "textarea" },
    // Cross-module linkage — optional record references stored for control-plane intelligence.
    { key: "linked_vector", label: "Linked Vector" },
    { key: "linked_case_id", label: "Case (UnifiedCases)" },
    { key: "linked_source_id", label: "Source (UnifiedSources)" },
    { key: "linked_gate_id", label: "Validation Gate" },
    { key: "linked_export_id", label: "Export" },
    { key: "linked_foia_id", label: "FOIA Request" },
    { key: "linked_integration_id", label: "Integration" },
    { key: "linked_contract_id", label: "Contract" },
    { key: "linked_vendor_id", label: "Vendor" },
    { key: "linked_anomaly_id", label: "Anomaly Flag" },
    { key: "linked_asset_id", label: "Infrastructure Asset" },
    { key: "linked_risk_id", label: "Continuity Risk" },
    { key: "linked_airspace_event_id", label: "Airspace Event" },
    { key: "linked_correlation_id", label: "Correlation Review" },
    { key: "linked_node_id", label: "Graph Node" },
    { key: "linked_edge_id", label: "Graph Edge" },
    { key: "linked_pattern_id", label: "Pattern Observation" },
    { key: "linked_witness_id", label: "Witness Report" },
  ];

  const openNew = () => { setEditing(null); setOpen(true); };
  const openEdit = (row) => { setEditing(stripDecorations(row)); setOpen(true); };
  const handleSave = async (data) => {
    if (editing?.id) await update({ id: editing.id, data });
    else await create(data);
    setOpen(false);
  };
  const handleStatusChange = async (task, status) => {
    await update({ id: task.id, data: { status } });
  };

  return (
    <div>
      <PageHeader
        icon={ListChecks}
        title="Federation Tasks"
        description="Task-centric control plane across all modules. Apply filters, then triage by program, urgency, table, or lifecycle."
        actions={<Button onClick={openNew}><Plus className="h-4 w-4 mr-2" />New Task</Button>}
      />

      <div className="flex items-center gap-2 mb-3 text-[11px] text-muted-foreground">
        <Info className="h-3.5 w-3.5" />
        Lifecycle &amp; role/sensitivity controls are UI-level in this MVP. Do not store real restricted data.
      </div>

      <DeadlineWarningBanner tasks={rollups.warnings} onSelect={openEdit} />

      <TaskFilterBar filters={filters} setFilter={setFilter} defs={filterDefs} onClear={clearFilters} hasActive={hasActive} />

      <div className="mb-4">
        <ViewToggle value={view} onChange={setView} />
      </div>

      {allTasks.length === 0 && !hasActive ? (
        <div className="rounded-xl border border-border bg-card p-8 text-center">
          <p className="text-sm text-muted-foreground">
            No Federation tasks have been created yet. Create a task from a program, case, source, validation gate, vector, export request, FOIA request, or module record.
          </p>
        </div>
      ) : (
        <>
          {view === "grouped" && <GroupedView grouped={grouped} role={role} onEdit={openEdit} onStatusChange={handleStatusChange} />}
          {view === "urgency" && <UrgencyView urgency={urgency} role={role} onEdit={openEdit} onStatusChange={handleStatusChange} />}
          {view === "flat" && <FlatTableView tasks={tasks} onEdit={openEdit} />}
          {view === "board" && <LifecycleBoardView board={board} role={role} onEdit={openEdit} onStatusChange={handleStatusChange} />}
        </>
      )}

      <RecordSheet open={open} onOpenChange={setOpen} title={editing?.id ? "Edit Task" : "New Task"} fields={FIELDS} initial={editing} onSave={handleSave} saving={saving} />
    </div>
  );
}

// Remove derived (_) fields before editing so they aren't written back.
function stripDecorations(row) {
  const clean = {};
  Object.keys(row).forEach((k) => { if (!k.startsWith("_")) clean[k] = row[k]; });
  return clean;
}