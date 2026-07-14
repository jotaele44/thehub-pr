import React from "react";
import { useEntityData } from "@/hooks/useEntityData";
import { ShieldAlert, CheckCircle2 } from "lucide-react";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import { SEVERITY, REVIEW_STATUS } from "@/lib/chips";

// Surfaces open GovernanceAlerts — high-severity entity changes recorded in the
// AuditLog without a corresponding validation gate update. Populated by the
// scheduled flagUngatedHighSeverityChanges watchdog.

const OPEN = ["Open", "Acknowledged"];

export default function GovernanceAlertsPanel() {
  const { rows: alerts, isLoading } = useEntityData("GovernanceAlerts");
  const open = alerts
    .filter((a) => OPEN.includes(a.review_status))
    .sort((x, y) => new Date(y.occurred_at || 0) - new Date(x.occurred_at || 0));

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center gap-2 mb-1">
        <ShieldAlert className="h-4 w-4 text-status-danger-fg" />
        <h3 className="text-sm font-semibold">Governance Alerts — Ungated High-Severity Changes</h3>
        {open.length > 0 && (
          <span className="ml-auto inline-flex items-center justify-center min-w-5 h-5 px-1.5 rounded-full bg-status-danger/20 text-status-danger-fg text-xs font-mono-id">
            {open.length}
          </span>
        )}
      </div>
      <p className="text-xs text-muted-foreground mb-4">
        High-severity entity modifications recorded without a corresponding validation gate update. Items are leads for review, not conclusions.
      </p>

      {isLoading ? (
        <p className="text-xs text-muted-foreground">Loading alerts…</p>
      ) : !open.length ? (
        <div className="flex items-center gap-2 text-xs text-status-success-fg">
          <CheckCircle2 className="h-4 w-4" /> No open governance alerts — high-severity changes are gate-aligned.
        </div>
      ) : (
        <div className="space-y-2">
          {open.slice(0, 8).map((a) => (
            <div key={a.id} className="flex items-start gap-3 rounded-lg border border-border bg-secondary/40 p-3">
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-1.5 mb-1">
                  <StatusChip map={SEVERITY} value={a.severity} />
                  <StatusChip map={REVIEW_STATUS} value={a.review_status} />
                  <span className="text-xs text-muted-foreground">{a.entity_name}</span>
                  <IdCode>{a.record_id}</IdCode>
                </div>
                <p className="text-sm text-foreground/90 truncate" title={a.summary}>{a.summary}</p>
                <div className="text-[11px] text-muted-foreground mt-0.5">
                  {a.actor || "unknown actor"} · {a.occurred_at ? new Date(a.occurred_at).toLocaleString() : "—"}
                </div>
              </div>
            </div>
          ))}
          {open.length > 8 && (
            <p className="text-xs text-muted-foreground">+{open.length - 8} more open alert(s).</p>
          )}
        </div>
      )}
    </div>
  );
}