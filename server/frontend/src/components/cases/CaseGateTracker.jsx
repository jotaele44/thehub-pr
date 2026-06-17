import React from "react";
import { cn } from "@/lib/utils";
import { CASE_STAGES } from "@/lib/case-gate-progress";
import StatusChip from "@/components/shared/StatusChip";
import { TIER } from "@/lib/chips";

// Visual progress tracker for a case's movement through validation stages.
// `progress` is the object returned by getCaseGateProgress.
export default function CaseGateTracker({ progress, compact = false }) {
  const { stageIndex, percent, label, bestTier, verifiedCount, sourceCount, blocked } = progress;

  const barColor = blocked
    ? "bg-amber-400"
    : percent >= 100
    ? "bg-emerald-400"
    : "bg-blue-400";

  return (
    <div className={compact ? "min-w-[180px]" : "space-y-2"}>
      {/* Progress bar */}
      <div className="h-1.5 w-full rounded-full bg-secondary overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all", barColor)}
          style={{ width: `${blocked ? 100 : percent}%` }}
        />
      </div>

      {/* Label row */}
      <div className="flex items-center gap-2 mt-1 text-xs">
        <span className={cn("font-medium", blocked ? "text-amber-300" : "text-foreground/90")}>
          {blocked ? "Contradicted — review" : label}
        </span>
        <span className="text-muted-foreground font-mono-id">{percent}%</span>
        {bestTier && <StatusChip map={TIER} value={bestTier} />}
        <span className="text-muted-foreground ml-auto">
          {verifiedCount}/{sourceCount} verified
        </span>
      </div>

      {/* Stage markers (full mode only) */}
      {!compact && (
        <div className="flex justify-between gap-1 pt-1">
          {CASE_STAGES.map((s, i) => (
            <div key={s.key} className="flex-1 text-center">
              <div
                className={cn(
                  "h-1.5 w-1.5 rounded-full mx-auto mb-1",
                  i <= stageIndex ? (blocked ? "bg-amber-400" : "bg-blue-400") : "bg-secondary"
                )}
              />
              <span
                className={cn(
                  "text-[10px] leading-tight",
                  i <= stageIndex ? "text-foreground/80" : "text-muted-foreground"
                )}
              >
                {s.label}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}