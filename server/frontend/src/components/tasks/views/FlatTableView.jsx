import React from "react";
import SearchableTable from "@/components/shared/SearchableTable";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import LinkageBadge from "../LinkageBadge";
import GapChips from "../GapChips";
import { TASK_LIFECYCLE, PRIORITY, SENSITIVITY } from "@/lib/chips";
import { cn } from "@/lib/utils";
import { format } from "date-fns";

export default function FlatTableView({ tasks, onEdit }) {
  const columns = [
    { key: "title", label: "Task", render: (r) => <span className={cn("font-medium", r._warning && "text-red-300")}>{r.title}</span> },
    { key: "_programLabel", label: "Program", render: (r) => <span className="text-muted-foreground text-xs">{r._programLabel}</span> },
    { key: "_status", label: "Status", render: (r) => <StatusChip map={TASK_LIFECYCLE} value={r._status} /> },
    { key: "_priority", label: "Priority", render: (r) => <StatusChip map={PRIORITY} value={r._priority} /> },
    { key: "due_date", label: "Due", render: (r) => r.due_date ? <span className={cn(r._overdue && "text-red-300")}>{format(new Date(r.due_date), "MMM d, yyyy")}</span> : <span className="text-muted-foreground">—</span> },
    { key: "assigned_to", label: "Assignee" },
    { key: "_sensitivity", label: "Sensitivity", render: (r) => r._sensitivity ? <StatusChip map={SENSITIVITY} value={r._sensitivity} /> : <span className="text-muted-foreground">—</span> },
    { key: "_linkage", label: "Linkage", render: (r) => <LinkageBadge label={r._linkage} /> },
    { key: "task_id", label: "Ref", render: (r) => <IdCode>{r.task_id}</IdCode> },
    { key: "_gaps", label: "Gaps", sortable: false, render: (r) => r._gaps.length ? <GapChips gaps={r._gaps} /> : <span className="text-muted-foreground">—</span> },
    { key: "updated_date", label: "Updated", render: (r) => r.updated_date ? format(new Date(r.updated_date), "MMM d") : "—" },
  ];

  return (
    <SearchableTable
      columns={columns}
      rows={tasks}
      onRowClick={onEdit}
      emptyTitle="No tasks"
      emptyDescription="No tasks match the current filters."
      initialSort={{ key: "due_date", dir: "asc" }}
    />
  );
}