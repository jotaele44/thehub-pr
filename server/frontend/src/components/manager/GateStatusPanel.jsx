import React from "react";
import { Info } from "lucide-react";
import StatusChip from "@/components/shared/StatusChip";
import { MANAGER_GATE_STATUS } from "@/lib/chips";

// Readiness gates, rendered exactly as the evaluator computed them.
//
// This panel has no control that changes a status, because there is no such
// control anywhere: status is derived from signed receipts server-side. An
// operator's note is displayed as commentary next to the machine verdict, never
// in place of it -- which is the point of gate binding.
export default function GateStatusPanel({ evidence }) {
  if (!evidence?.gates?.length) {
    return (
      <p className="text-sm text-muted-foreground">
        No gate evidence yet. Gates populate as operations produce signed receipts.
      </p>
    );
  }

  return (
    <div className="space-y-2" data-testid="gate-panel">
      <p className="text-xs text-muted-foreground">
        Derived from verified receipts only. Notes are advisory and cannot change a status.
      </p>
      <ul className="divide-y divide-border rounded-lg border border-border">
        {evidence.gates.map((gate) => (
          <li key={gate.gate_id} className="p-3" data-gate-id={gate.gate_id}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium font-mono">{gate.gate_id}</p>
                {gate.requirement && (
                  <p className="text-xs text-muted-foreground mt-0.5">{gate.requirement}</p>
                )}
              </div>
              <StatusChip map={MANAGER_GATE_STATUS} value={gate.status} />
            </div>

            {gate.status_reason && (
              <p className="text-xs text-muted-foreground mt-1.5">{gate.status_reason}</p>
            )}

            {gate.derived_from?.length > 0 && (
              <p className="text-[11px] text-muted-foreground mt-1.5 font-mono">
                {gate.derived_from.length} verified receipt
                {gate.derived_from.length === 1 ? "" : "s"}:{" "}
                {gate.derived_from.map((source) => source.receipt_sha256.slice(0, 8)).join(", ")}
              </p>
            )}

            {gate.annotations?.map((annotation) => (
              <p
                key={`${annotation.author}-${annotation.recorded_at}`}
                className="text-[11px] text-muted-foreground mt-1.5 flex items-start gap-1"
              >
                <Info className="h-3 w-3 mt-0.5 shrink-0" />
                <span>
                  <span className="font-medium">{annotation.author}</span> (note, not evidence):{" "}
                  {annotation.note}
                </span>
              </p>
            ))}
          </li>
        ))}
      </ul>
    </div>
  );
}
