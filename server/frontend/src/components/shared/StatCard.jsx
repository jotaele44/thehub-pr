import React from "react";
import { cn } from "@/lib/utils";

export default function StatCard({ label, value, icon: Icon, accent = "text-foreground", sub, alert }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{label}</span>
        {Icon && <Icon className={cn("h-4 w-4", alert ? "text-red-400" : "text-muted-foreground")} />}
      </div>
      <div className={cn("text-2xl font-semibold font-mono-id", accent)}>{value}</div>
      {sub && <div className="text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}