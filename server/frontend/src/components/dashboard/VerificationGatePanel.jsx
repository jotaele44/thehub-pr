import React from "react";
import { useVerificationGate } from "@/hooks/useVerificationGate";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import { Button } from "@/components/ui/button";
import { ShieldCheck, Check, AlertCircle, ExternalLink, Inbox } from "lucide-react";

const SYNC = {
  New: "bg-status-info/15 text-status-info-fg border-status-info/30",
  Updated: "bg-status-info/15 text-status-info-fg border-status-info/30",
  NeedsReview: "bg-status-warning/15 text-status-warning-fg border-status-warning/30",
};

const MODULE = {
  "MoneySweep-PR": "bg-status-process/15 text-status-process-fg border-status-process/30",
  "AguaYLuz-PR": "bg-cyan-500/15 text-cyan-300 border-cyan-500/30",
};

function itemMeta(it) {
  if (it.module === "MoneySweep-PR") {
    return [it.agency_name, it.vendor_name].filter(Boolean).join(" · ") || it.summary;
  }
  return [it.facility_name, it.municipality, it.event_type].filter(Boolean).join(" · ") || it.summary;
}

// Federation verification gate on the dashboard: analysts verify incoming
// MoneySweep / AguaYLuz feed items before they're eligible to hit the ledger.
export default function VerificationGatePanel() {
  const { pending, counts, isLoading, saving, verify, reject } = useVerificationGate();

  return (
    <div className="rounded-xl border border-border bg-card p-5 mb-8">
      <div className="flex items-center gap-2 mb-1">
        <ShieldCheck className="h-4 w-4 text-status-success-fg" />
        <h3 className="text-sm font-semibold">Verification Gate</h3>
        <span className="ml-auto text-xs text-muted-foreground">
          {counts.moneysweep} MoneySweep · {counts.aguayluz} AguaYLuz pending · {counts.verifiedReady} verified
        </span>
      </div>
      <p className="text-xs text-muted-foreground mb-4">
        Incoming feed records must be verified by an analyst before they can be promoted to the main ledger.
      </p>

      {isLoading ? (
        <p className="text-xs text-muted-foreground py-6 text-center">Loading queue…</p>
      ) : !pending.length ? (
        <div className="flex flex-col items-center gap-1 py-6 text-center">
          <Inbox className="h-5 w-5 text-muted-foreground" />
          <p className="text-xs text-muted-foreground">Nothing awaiting verification. New feed items will appear here.</p>
        </div>
      ) : (
        <div className="space-y-2 max-h-96 overflow-auto pr-1">
          {pending.map((it) => (
            <div key={it.id} className="rounded-lg border border-border bg-background/40 p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <StatusChip map={MODULE} value={it.module} />
                    <StatusChip map={SYNC} value={it.sync_status} />
                    {it.evidence_tier && <span className="text-[10px] font-mono-id text-muted-foreground">{it.evidence_tier}</span>}
                  </div>
                  <div className="font-medium text-sm mt-1 truncate">{it.title}</div>
                  <div className="text-xs text-muted-foreground mt-0.5 truncate">{itemMeta(it)}</div>
                  <div className="mt-1"><IdCode>{it.feed_item_id}</IdCode></div>
                </div>
                <div className="flex flex-col gap-1.5 shrink-0">
                  <Button size="sm" disabled={saving} onClick={() => verify(it)}>
                    <Check className="h-3.5 w-3.5 mr-1" /> Verify
                  </Button>
                  <Button size="sm" variant="ghost" disabled={saving} onClick={() => reject(it)}>
                    <AlertCircle className="h-3.5 w-3.5 mr-1" /> Flag
                  </Button>
                  {it.source_url && (
                    <a href={it.source_url} target="_blank" rel="noreferrer" className="text-xs text-status-info-fg flex items-center gap-1 px-2">
                      <ExternalLink className="h-3 w-3" /> Source
                    </a>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}