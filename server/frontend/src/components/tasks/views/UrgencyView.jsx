import React from "react";
import TaskCard from "../TaskCard";
import { AlertOctagon, Ban, CalendarDays, CalendarRange, Flame, MapPinOff, CircleHelp } from "lucide-react";

const ICONS = {
  "Overdue": AlertOctagon,
  "Blocked": Ban,
  "Due Today": CalendarDays,
  "Due This Week": CalendarRange,
  "High Priority": Flame,
  "Unassigned / Needs Mapping": MapPinOff,
  "No Due Date": CircleHelp,
};

const ALERT = new Set(["Overdue", "Blocked"]);

export default function UrgencyView({ urgency, role, onEdit, onStatusChange }) {
  const active = urgency.filter((b) => b.tasks.length > 0);
  if (!active.length) {
    return <p className="text-sm text-muted-foreground py-8 text-center">No tasks match the current filters.</p>;
  }
  return (
    <div className="space-y-5">
      {active.map((bucket) => {
        const Icon = ICONS[bucket.label] || CircleHelp;
        const alert = ALERT.has(bucket.label);
        return (
          <div key={bucket.label}>
            <div className="flex items-center gap-2 mb-2">
              <Icon className={alert ? "h-4 w-4 text-status-danger-fg" : "h-4 w-4 text-muted-foreground"} />
              <h3 className={alert ? "text-sm font-semibold text-status-danger-fg" : "text-sm font-semibold text-foreground"}>{bucket.label}</h3>
              <span className="text-xs text-muted-foreground font-mono-id">{bucket.tasks.length}</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
              {bucket.tasks.map((t) => (
                <TaskCard key={t.id} task={t} role={role} onEdit={onEdit} onStatusChange={onStatusChange} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}