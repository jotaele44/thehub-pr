import React from "react";
import { CheckCircle2 } from "lucide-react";
import { MODULES, domainAccent } from "@/lib/federation";
import { cn } from "@/lib/utils";

// Parent + 5 child modules, all confirmed connected to the INTSYS-PR / thehub-pr transition layer.
const ROWS = [
  { name: "INTSYS-PR", domain: "ControlPlane", oldName: "thehub-pr", blurb: "Parent control plane" },
  ...MODULES,
];

export default function ModuleParityList() {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-3">
        Module Parity · {ROWS.length} modules connected
      </div>
      <div className="space-y-2">
        {ROWS.map((m) => {
          const accent = domainAccent(m.domain);
          return (
            <div key={m.name} className="flex items-center gap-3 rounded-lg border border-border/60 bg-secondary/30 px-3 py-2">
              <span className={cn("h-2 w-2 rounded-full shrink-0", accent.dot)} />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-foreground truncate">{m.name}</div>
                <div className="text-xs text-muted-foreground truncate">{m.blurb} · from {m.oldName}</div>
              </div>
              <span className="flex items-center gap-1 text-xs text-status-success-fg shrink-0">
                <CheckCircle2 className="h-3.5 w-3.5" /> Connected
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}