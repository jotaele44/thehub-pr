import React from "react";
import StatusChip from "@/components/shared/StatusChip";
import { GATE_STATUS } from "@/lib/chips";

export default function GateChecklist({ gates }) {
  const sorted = [...gates].sort((a, b) => (a.gate_name || "").localeCompare(b.gate_name || ""));
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-3">
        thehub-pr Transition Parity Gates
      </div>
      <div className="space-y-2">
        {sorted.map((g) => (
          <div key={g.gate_id} className="rounded-lg border border-border/60 bg-secondary/30 px-3 py-2.5">
            <div className="flex items-center justify-between gap-3">
              <span className="font-mono-id text-xs text-foreground truncate">{g.gate_name}</span>
              <StatusChip map={GATE_STATUS} value={g.status} />
            </div>
            <p className="text-xs text-muted-foreground mt-1">{g.requirement}</p>
          </div>
        ))}
        {sorted.length === 0 && <p className="text-xs text-muted-foreground">No gates found.</p>}
      </div>
    </div>
  );
}