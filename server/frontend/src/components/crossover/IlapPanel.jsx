import React from "react";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import EmptyState from "@/components/shared/EmptyState";
import { CONFIDENCE, SENSITIVITY } from "@/lib/chips";
import { MapPin } from "lucide-react";

// ILAP candidates / POIs are represented as GraphNodes with controlled node_type values.
export default function IlapPanel({ ilapNodes }) {
  if (!ilapNodes.length) {
    return (
      <EmptyState
        icon={MapPin}
        title="No ILAP candidates / POIs yet"
        description="ILAP candidates and points of interest are represented as GraphNodes with node_type ILAP_CANDIDATE, POI, LAND_DEVELOPMENT_SITE, or INFRASTRUCTURE_ADJACENT_POI. Add such nodes in Spiderweb to surface them here with their cross-module links."
      />
    );
  }
  return (
    <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
      {ilapNodes.map((n) => (
        <div key={n.id} className="rounded-xl border border-border bg-card p-4 space-y-2">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="text-sm font-medium truncate">{n.label}</div>
              <IdCode>{n.node_id || n.id}</IdCode>
            </div>
            <StatusChip map={{ ILAP_CANDIDATE: "bg-lime-500/15 text-lime-300 border-lime-500/30", POI: "bg-teal-500/15 text-teal-300 border-teal-500/30", LAND_DEVELOPMENT_SITE: "bg-amber-500/15 text-amber-300 border-amber-500/30", INFRASTRUCTURE_ADJACENT_POI: "bg-sky-500/15 text-sky-300 border-sky-500/30" }} value={n.node_type} />
          </div>
          <div className="flex flex-wrap gap-1.5">
            {n.confidence && <StatusChip map={CONFIDENCE} value={n.confidence} />}
            {n.sensitivity && <StatusChip map={SENSITIVITY} value={n.sensitivity} />}
            {n.municipality && <span className="text-xs text-muted-foreground inline-flex items-center gap-1"><MapPin className="h-3 w-3" />{n.municipality}</span>}
          </div>
          {(n.latitude || n.longitude) && (
            <div className="text-xs font-mono-id text-muted-foreground">{n.latitude ?? "—"}, {n.longitude ?? "—"}</div>
          )}
          {n.summary && <p className="text-xs text-foreground/80">{n.summary}</p>}
          <p className="text-[11px] text-muted-foreground">Cross-module links surface in the matrix and pair panels via graph edges and shared attributes.</p>
        </div>
      ))}
    </div>
  );
}