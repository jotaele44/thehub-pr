import React from "react";
import { cn } from "@/lib/utils";
import { domainAccent } from "@/lib/federation";

function Metric({ label, value, alert }) {
  if (!value) return <span className="text-[11px] text-muted-foreground/60">{label} 0</span>;
  return (
    <span className={cn("text-[11px]", alert ? "text-status-danger-fg font-medium" : "text-muted-foreground")}>
      {label} <span className="font-mono-id">{value}</span>
    </span>
  );
}

export default function GroupHeaderMetrics({ label, domain, metrics }) {
  const accent = domainAccent(domain);
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 w-full">
      <span className={cn("h-2.5 w-2.5 rounded-full shrink-0", accent.dot)} />
      <span className="text-sm font-semibold text-foreground">{label}</span>
      <span className="text-[11px] text-muted-foreground">· {metrics.total} task{metrics.total === 1 ? "" : "s"}</span>
      <span className="hidden sm:inline text-muted-foreground/30">|</span>
      <Metric label="Open" value={metrics.open} />
      <Metric label="Overdue" value={metrics.overdue} alert />
      <Metric label="Blocked" value={metrics.blocked} alert={metrics.blocked > 0} />
      <Metric label="High" value={metrics.high} />
      <Metric label="Due wk" value={metrics.dueThisWeek} />
      <Metric label="Gaps" value={metrics.gaps} alert={metrics.gaps > 0} />
    </div>
  );
}