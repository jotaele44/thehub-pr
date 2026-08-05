import React from "react";
import { useEntityData } from "@/hooks/useEntityData";
import { ShieldAlert, CheckCircle2 } from "lucide-react";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import { SEVERITY, REVIEW_STATUS } from "@/lib/chips";

// Surfaces open GovernanceAlerts across the federation. The collection is populated
// by `hub ingest` from each producer's canonical `alerts` stream
// (src/hub/ingest.py `_UI_PROJECTIONS`), so a row here is a producer's operational
// alert — an AguaYLuz contamination or seismic alert, say — not a hub audit finding.
// Per-module triage lives on that module's page; this is the cross-module rollup.

const OPEN = ["Open", "Acknowledged"];

// Producer alerts carry a 0–5 operational severity; the hub's chips speak
// Low/Medium/High/Critical. Same banding as `_SEVERITY_BAND` in src/hub/ingest.py.
const SEVERITY_BAND = { 0: "Low", 1: "Low", 2: "Medium", 3: "High", 4: "Critical", 5: "Critical" };
const severityLabel = (s) => (typeof s === "number" ? SEVERITY_BAND[s] : s);

export default function GovernanceAlertsPanel() {
  const { rows: alerts, isLoading } = useEntityData("GovernanceAlerts");
  const open = alerts
    .filter((a) => OPEN.includes(a.review_status))
    .sort((x, y) => new Date(y.occurred_at || 0) - new Date(x.occurred_at || 0));

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center gap-2 mb-1">
        <ShieldAlert className="h-4 w-4 text-status-danger-fg" />
        <h3 className="text-sm font-semibold">Open Alerts — Federated Producer Modules</h3>
        {open.length > 0 && (
          <span className="ml-auto inline-flex items-center justify-center min-w-5 h-5 px-1.5 rounded-full bg-status-danger/20 text-status-danger-fg text-xs font-mono-id">
            {open.length}
          </span>
        )}
      </div>
      <p className="text-xs text-muted-foreground mb-4">
        Operational alerts still open across every producer&apos;s exported alert stream. Items are leads for review, not conclusions.
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
                  <StatusChip map={SEVERITY} value={severityLabel(a.severity)} />
                  <StatusChip map={REVIEW_STATUS} value={a.review_status} />
                  <span className="text-xs text-muted-foreground">{a.module || a.entity_name}</span>
                  {a.record_id && <IdCode>{a.record_id}</IdCode>}
                </div>
                <p className="text-sm text-foreground/90 truncate" title={a.summary}>{a.summary}</p>
                {/* Which producer exported this alert — the rollup spans modules, so
                    the source matters more than an `actor` these rows never carry. */}
                <div className="text-[11px] text-muted-foreground mt-0.5">
                  {(a._producers || []).join(", ") || "unattributed producer"} · {a.occurred_at ? new Date(a.occurred_at).toLocaleString() : "—"}
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