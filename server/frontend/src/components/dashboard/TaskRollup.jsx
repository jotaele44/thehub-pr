import React from "react";
import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useTaskControlPlane } from "@/hooks/useTaskControlPlane";
import { domainAccent } from "@/lib/federation";
import StatCard from "@/components/shared/StatCard";
import { ListChecks, AlertOctagon, Ban, Flame, CalendarDays, MapPinOff, ArrowRight } from "lucide-react";
import { format } from "date-fns";

// scope: undefined => federation-wide; otherwise a program key for module-scoped rollups.
export default function TaskRollup({ scope }) {
  const { grouped, rollups } = useTaskControlPlane();

  if (scope) {
    const group = grouped.find((g) => g.key === scope);
    if (!group) return null;
    const m = group.metrics;
    return (
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold flex items-center gap-2"><ListChecks className="h-4 w-4" /> Module Tasks</h3>
          <Link to={`/tasks?program=${scope}`} className="text-xs text-sky-300 hover:underline flex items-center gap-1">
            Open <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <MiniStat label="Open" value={m.open} />
          <MiniStat label="Overdue" value={m.overdue} alert />
          <MiniStat label="Blocked" value={m.blocked} alert={m.blocked > 0} />
          <MiniStat label="High Priority" value={m.high} />
          <MiniStat label="Due This Week" value={m.dueThisWeek} />
          <MiniStat label="Gaps" value={m.gaps} alert={m.gaps > 0} />
        </div>
        {group.metrics.total > 0 && (
          <div className="mt-3 pt-3 border-t border-border space-y-1.5">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Recently updated</p>
            {[...group.tasks]
              .sort((a, b) => new Date(b.updated_date || 0) - new Date(a.updated_date || 0))
              .slice(0, 4)
              .map((t) => (
                <div key={t.id} className="flex items-center justify-between text-xs">
                  <span className="truncate text-muted-foreground mr-2">{t.title}</span>
                  <span className="text-[10px] text-muted-foreground/70 shrink-0">{t.updated_date ? format(new Date(t.updated_date), "MMM d") : ""}</span>
                </div>
              ))}
          </div>
        )}
      </div>
    );
  }

  // Federation-wide rollups
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard label="Open Tasks" value={rollups.open} icon={ListChecks} />
        <StatCard label="Overdue" value={rollups.overdue} icon={AlertOctagon} accent="text-red-300" alert={rollups.overdue > 0} />
        <StatCard label="Blocked" value={rollups.blocked} icon={Ban} accent="text-red-300" alert={rollups.blocked > 0} />
        <StatCard label="High Priority" value={rollups.high} icon={Flame} accent="text-amber-300" />
        <StatCard label="Due This Week" value={rollups.dueThisWeek} icon={CalendarDays} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 rounded-xl border border-border bg-card p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold">Open Tasks by Program</h3>
            <Link to="/tasks" className="text-xs text-sky-300 hover:underline flex items-center gap-1">Task control plane <ArrowRight className="h-3 w-3" /></Link>
          </div>
          <div className="space-y-2">
            {rollups.byProgram.map((p) => {
              const accent = domainAccent(p.domain);
              return (
                <Link key={p.key} to={`/tasks?program=${p.key}`} className="flex items-center gap-2 group">
                  <span className={cn("h-2 w-2 rounded-full shrink-0", accent.dot)} />
                  <span className="text-xs text-muted-foreground group-hover:text-foreground transition-colors">{p.label}</span>
                  <div className="flex-1 h-px bg-border" />
                  <span className="text-xs font-mono-id text-foreground">{p.open}</span>
                </Link>
              );
            })}
          </div>
          {rollups.unassigned > 0 && (
            <div className="mt-3 flex items-center gap-2 text-xs text-amber-300">
              <MapPinOff className="h-3.5 w-3.5" />
              {rollups.unassigned} unassigned task gap{rollups.unassigned === 1 ? "" : "s"} need program mapping
            </div>
          )}
        </div>

        <div className="rounded-xl border border-border bg-card p-5">
          <h3 className="text-sm font-semibold mb-3">Recent Task Changes</h3>
          <div className="space-y-2">
            {rollups.recent.map((t) => (
              <Link key={t.id} to="/tasks" className="flex items-center justify-between text-xs group">
                <span className="truncate text-muted-foreground group-hover:text-foreground mr-2 transition-colors">{t.title}</span>
                <span className="text-[10px] text-muted-foreground/70 shrink-0">{t.updated_date ? format(new Date(t.updated_date), "MMM d") : ""}</span>
              </Link>
            ))}
            {!rollups.recent.length && <p className="text-xs text-muted-foreground">No tasks yet.</p>}
          </div>
          <div className="mt-3 pt-3 border-t border-border">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-2">Tasks by Linked Entity</p>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(rollups.linkageCounts).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
                <span key={k} className="text-[10px] px-1.5 py-0.5 rounded border border-border bg-secondary/40 text-muted-foreground">{k} <span className="font-mono-id text-foreground">{v}</span></span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MiniStat({ label, value, alert }) {
  return (
    <div className="rounded-lg border border-border bg-secondary/30 p-2.5">
      <div className={cn("text-lg font-semibold font-mono-id", alert && value > 0 ? "text-red-300" : "text-foreground")}>{value}</div>
      <div className="text-[10px] text-muted-foreground uppercase tracking-wide">{label}</div>
    </div>
  );
}