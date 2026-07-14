import React from "react";
import { AlarmClock, ChevronRight } from "lucide-react";
import { format } from "date-fns";
import { cn } from "@/lib/utils";

// Highlights high/critical priority tasks due within 48h (or overdue) up top.
export default function DeadlineWarningBanner({ tasks = [], onSelect }) {
  if (!tasks.length) return null;
  return (
    <div className="rounded-xl border border-status-danger/40 bg-status-danger/[0.06] p-4 mb-4">
      <div className="flex items-center gap-2 mb-2">
        <AlarmClock className="h-4 w-4 text-status-danger-fg" />
        <h3 className="text-sm font-semibold text-status-danger-fg">Deadline Warnings</h3>
        <span className="text-xs text-status-danger-fg/80">
          {tasks.length} high-priority task{tasks.length === 1 ? "" : "s"} due within 48 hours or overdue
        </span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
        {tasks.slice(0, 6).map((t) => (
          <button
            key={t.id}
            onClick={() => onSelect?.(t)}
            className="flex items-center justify-between gap-2 text-left rounded-lg border border-status-danger/25 bg-card/60 px-3 py-2 hover:bg-card transition-colors"
          >
            <div className="min-w-0">
              <p className="text-xs font-medium text-foreground truncate">{t.title}</p>
              <p className="text-[11px] text-muted-foreground">
                {t._programLabel} · {t._priority}
                {t.due_date && (
                  <span className={cn(t._overdue && "text-status-danger-fg")}> · {format(new Date(t.due_date), "MMM d")}</span>
                )}
              </p>
            </div>
            <ChevronRight className="h-4 w-4 text-status-danger-fg/70 shrink-0" />
          </button>
        ))}
      </div>
    </div>
  );
}