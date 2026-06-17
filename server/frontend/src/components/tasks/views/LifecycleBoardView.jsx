import React from "react";
import { cn } from "@/lib/utils";
import StatusChip from "@/components/shared/StatusChip";
import { TASK_LIFECYCLE, PRIORITY } from "@/lib/chips";
import LinkageBadge from "../LinkageBadge";
import GapChips from "../GapChips";
import { getTaskLifecycleOptions } from "@/lib/task-utils";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AlarmClock } from "lucide-react";
import { format } from "date-fns";

export default function LifecycleBoardView({ board, role, onEdit, onStatusChange }) {
  return (
    <div className="overflow-x-auto pb-2">
      <div className="flex gap-3 min-w-max">
        {board.map((col) => (
          <div key={col.status} className="w-72 shrink-0">
            <div className="flex items-center justify-between px-2 py-2 mb-2 rounded-lg border border-border bg-card">
              <StatusChip map={TASK_LIFECYCLE} value={col.status} />
              <span className="text-xs text-muted-foreground font-mono-id">{col.tasks.length}</span>
            </div>
            <div className="space-y-2">
              {col.tasks.map((t) => {
                const opts = getTaskLifecycleOptions(t._status, role);
                return (
                  <div
                    key={t.id}
                    onClick={() => onEdit?.(t)}
                    className={cn(
                      "rounded-lg border bg-card p-2.5 cursor-pointer hover:bg-secondary/40 transition-colors",
                      t._warning ? "border-red-500/50" : "border-border"
                    )}
                  >
                    {t._warning && <div className="flex items-center gap-1 mb-1 text-[10px] text-red-300"><AlarmClock className="h-3 w-3" />Due soon · high priority</div>}
                    <p className="text-xs font-medium leading-snug mb-1.5">{t.title}</p>
                    <div className="flex flex-wrap items-center gap-1 mb-1">
                      <StatusChip map={PRIORITY} value={t._priority} />
                      <LinkageBadge label={t._linkage} />
                    </div>
                    <div className="text-[10px] text-muted-foreground">{t._programLabel}{t.due_date ? ` · ${format(new Date(t.due_date), "MMM d")}` : ""}</div>
                    <GapChips gaps={t._gaps} className="mt-1" />
                    {opts.length > 0 && (
                      <div className="mt-1.5" onClick={(e) => e.stopPropagation()}>
                        <Select onValueChange={(v) => onStatusChange?.(t, v)}>
                          <SelectTrigger className="h-6 text-[11px] bg-secondary/50 border-border"><SelectValue placeholder="Move…" /></SelectTrigger>
                          <SelectContent>
                            {opts.map((o) => <SelectItem key={o} value={o} className="text-xs">{o}</SelectItem>)}
                          </SelectContent>
                        </Select>
                      </div>
                    )}
                  </div>
                );
              })}
              {!col.tasks.length && <p className="text-[11px] text-muted-foreground/60 px-2 py-3">Empty</p>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}