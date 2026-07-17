import React from "react";
import StatusChip from "@/components/shared/StatusChip";
import { TIER } from "@/lib/chips";

export default function EvidenceStandardsCard({ standards }) {
  const sorted = [...standards].sort((a, b) => (a.tier || "").localeCompare(b.tier || ""));
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Evidence Standards</span>
        <StatusChip map={{ Populated: "bg-status-success/15 text-status-success-fg border-status-success/30", Empty: "bg-status-danger/15 text-status-danger-fg border-status-danger/30" }} value={sorted.length === 4 ? "Populated" : (sorted.length === 0 ? "Empty" : "Partial")} />
      </div>
      <div className="space-y-2">
        {sorted.map((s) => (
          <div key={s.standard_id} className="flex items-start gap-3 rounded-lg border border-border/60 bg-secondary/30 px-3 py-2">
            <StatusChip map={TIER} value={s.tier} />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-foreground">{s.label} <span className="text-xs text-muted-foreground">· {s.weight}</span></div>
              <div className="text-xs text-muted-foreground">{s.definition}</div>
            </div>
          </div>
        ))}
        {sorted.length === 0 && <p className="text-xs text-muted-foreground">EvidenceStandards not seeded.</p>}
      </div>
    </div>
  );
}