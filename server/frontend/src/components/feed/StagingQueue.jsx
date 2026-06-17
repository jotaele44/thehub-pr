import React from "react";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import { Button } from "@/components/ui/button";
import { Check, Clock, AlertCircle, ExternalLink, ShieldCheck } from "lucide-react";

const SYNC = {
  New: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  Updated: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  Matched: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  NeedsReview: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  Verified: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  Promoted: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  Deferred: "bg-muted text-muted-foreground border-border",
  Failed: "bg-red-500/15 text-red-300 border-red-500/30",
};

// renderMeta(item) -> small inline metadata node (module-specific).
export default function StagingQueue({ items, onSetStatus, renderMeta, saving }) {
  if (!items.length) {
    return <p className="text-sm text-muted-foreground p-6 text-center">Staging queue is empty. Run a refetch to pull new records.</p>;
  }
  return (
    <div className="space-y-2">
      {items.map((it) => (
        <div key={it.id} className="rounded-lg border border-border bg-card p-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <StatusChip map={SYNC} value={it.sync_status} />
                <span className="text-xs text-muted-foreground">{it.source_system}</span>
                {it.evidence_tier && <span className="text-[10px] font-mono-id text-muted-foreground">{it.evidence_tier}</span>}
              </div>
              <div className="font-medium text-sm mt-1 truncate">{it.title}</div>
              <div className="text-xs text-muted-foreground mt-0.5">{renderMeta ? renderMeta(it) : it.summary}</div>
              <div className="mt-1"><IdCode>{it.feed_item_id}</IdCode></div>
            </div>
            <div className="flex flex-col gap-1.5 shrink-0">
              {it.sync_status !== "Verified" && (
                <Button size="sm" disabled={saving} onClick={() => onSetStatus(it, "Verified")}>
                  <ShieldCheck className="h-3.5 w-3.5 mr-1" /> Verify
                </Button>
              )}
              <Button
                size="sm"
                variant="outline"
                disabled={saving || it.sync_status !== "Verified"}
                title={it.sync_status !== "Verified" ? "Verify before promoting to the ledger" : undefined}
                onClick={() => onSetStatus(it, "Promoted")}
              >
                <Check className="h-3.5 w-3.5 mr-1" /> Promote
              </Button>
              <Button size="sm" variant="ghost" disabled={saving} onClick={() => onSetStatus(it, "NeedsReview")}>
                <AlertCircle className="h-3.5 w-3.5 mr-1" /> Review
              </Button>
              <Button size="sm" variant="ghost" disabled={saving} onClick={() => onSetStatus(it, "Deferred")}>
                <Clock className="h-3.5 w-3.5 mr-1" /> Defer
              </Button>
              {it.source_url && (
                <a href={it.source_url} target="_blank" rel="noreferrer" className="text-xs text-sky-300 flex items-center gap-1 px-2">
                  <ExternalLink className="h-3 w-3" /> Source
                </a>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}