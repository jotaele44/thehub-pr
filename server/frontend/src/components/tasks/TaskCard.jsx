import React from "react";
import { cn } from "@/lib/utils";
import StatusChip from "@/components/shared/StatusChip";
import { TASK_LIFECYCLE, PRIORITY, SENSITIVITY } from "@/lib/chips";
import LinkageBadge from "./LinkageBadge";
import GapChips from "./GapChips";
import { getTaskLifecycleOptions } from "@/lib/task-utils";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AlarmClock, CalendarClock, User, Clock } from "lucide-react";
import { format } from "date-fns";

export default function TaskCard({ task, role = "admin", onEdit, onStatusChange }) {
  const warning = task._warning;
  const lifecycleOpts = getTaskLifecycleOptions(task._status, role);

  return (
    <div
      onClick={() => onEdit?.(task)}
      className={cn(
        "rounded-lg border bg-card p-3 transition-colors cursor-pointer hover:bg-secondary/40",
        warning
          ? "border-red-500/50 ring-1 ring-red-500/30 bg-red-500/[0.04]"
          : "border-border"
      )}
    >
      {warning && (
        <div className="flex items-center gap-1.5 mb-2 text-[11px] font-medium text-red-300">
          <AlarmClock className="h-3.5 w-3.5" />
          {task._overdue ? "Overdue · high priority" : "Due within 48h · high priority"}
        </div>
      )}

      <div className="flex items-start justify-between gap-2 mb-2">
        <p className="text-sm font-medium leading-snug text-foreground">{task.title}</p>
        <StatusChip map={PRIORITY} value={task._priority} />
      </div>

      <div className="flex flex-wrap items-center gap-1.5 mb-2">
        <StatusChip map={TASK_LIFECYCLE} value={task._status} />
        <span className="text-[10px] text-muted-foreground">{task._programLabel}</span>
        <LinkageBadge label={task._linkage} />
        {task._sensitivity && <StatusChip map={SENSITIVITY} value={task._sensitivity} />}
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
        <span className={cn("inline-flex items-center gap-1", task._overdue && "text-red-300")}>
          <CalendarClock className="h-3 w-3" />
          {task.due_date ? format(new Date(task.due_date), "MMM d, yyyy") : "No due date"}
        </span>
        {task.assigned_to && (
          <span className="inline-flex items-center gap-1"><User className="h-3 w-3" />{task.assigned_to}</span>
        )}
        {task.updated_date && (
          <span className="inline-flex items-center gap-1"><Clock className="h-3 w-3" />{format(new Date(task.updated_date), "MMM d")}</span>
        )}
      </div>

      <GapChips gaps={task._gaps} className="mt-2" />

      {lifecycleOpts.length > 0 && (
        <div className="mt-2 pt-2 border-t border-border" onClick={(e) => e.stopPropagation()}>
          <Select onValueChange={(v) => onStatusChange?.(task, v)}>
            <SelectTrigger className="h-7 text-xs bg-secondary/50 border-border">
              <SelectValue placeholder="Move to…" />
            </SelectTrigger>
            <SelectContent>
              {lifecycleOpts.map((o) => (
                <SelectItem key={o} value={o} className="text-xs">{o}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
    </div>
  );
}