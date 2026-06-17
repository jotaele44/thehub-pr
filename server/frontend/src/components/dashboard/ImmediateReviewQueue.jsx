import React, { useMemo } from "react";
import { useEntityData } from "@/hooks/useEntityData";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import EmptyState from "@/components/shared/EmptyState";
import { SEVERITY, CONFIDENCE, REVIEW_STATUS } from "@/lib/chips";
import { AlertOctagon, ShieldCheck } from "lucide-react";

// Automated rule: high structural risk but low confidence — a mismatch that
// warrants source-backed review before any conclusion. Already-closed flags
// (Rejected / FalsePositive) are excluded from the queue.
const HIGH_SEVERITY = ["High", "Critical"];
const CLOSED = ["Rejected", "FalsePositive"];

const needsImmediateReview = (a) =>
  HIGH_SEVERITY.includes(a.severity) &&
  a.confidence === "Low" &&
  !CLOSED.includes(a.review_status);

export default function ImmediateReviewQueue() {
  const { rows: anomalies } = useEntityData("AnomalyFlags");

  const queue = useMemo(
    () => anomalies.filter(needsImmediateReview),
    [anomalies]
  );

  return (
    <div className="rounded-xl border border-red-500/30 bg-card p-5">
      <div className="flex items-center gap-2 mb-1">
        <AlertOctagon className="h-4 w-4 text-red-300" />
        <h3 className="text-sm font-semibold">Needs Immediate Review</h3>
        <span className="ml-auto text-sm font-semibold font-mono-id text-red-300">{queue.length}</span>
      </div>
      <p className="text-xs text-muted-foreground mb-4">
        Auto-flagged anomalies with high/critical severity but low confidence — a risk/evidence mismatch requiring source-backed review before any conclusion.
      </p>

      {!queue.length ? (
        <EmptyState
          icon={ShieldCheck}
          title="Queue clear"
          description="No high-severity / low-confidence anomalies are awaiting review."
        />
      ) : (
        <div className="space-y-2">
          {queue.map((a) => (
            <div key={a.id} className="rounded-lg border border-border bg-secondary/40 p-3">
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <IdCode>{a.flag_id}</IdCode>
                <span className="text-xs text-muted-foreground">{a.flag_type}</span>
                <span className="text-xs text-muted-foreground">·</span>
                <span className="text-xs text-muted-foreground">Severity</span>
                <StatusChip map={SEVERITY} value={a.severity} />
                <span className="text-xs text-muted-foreground">Confidence</span>
                <StatusChip map={CONFIDENCE} value={a.confidence} />
                <StatusChip map={REVIEW_STATUS} value={a.review_status} className="ml-auto" />
              </div>
              {a.rationale && <p className="text-xs text-foreground/90">{a.rationale}</p>}
              {a.contract_id && (
                <div className="text-xs text-muted-foreground mt-1">
                  Contract <IdCode>{a.contract_id}</IdCode>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}