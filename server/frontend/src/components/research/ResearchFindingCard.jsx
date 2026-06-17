import React from "react";
import StatusChip from "@/components/shared/StatusChip";
import { CONFIDENCE, TIER } from "@/lib/chips";
import { Card } from "@/components/ui/card";
import { ExternalLink } from "lucide-react";

// Renders a single source-backed lead returned by the research assistant.
// Findings are presented as leads/candidates requiring review — not conclusions.
export default function ResearchFindingCard({ finding, index }) {
  return (
    <Card className="p-4 space-y-2">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2">
          <span className="font-mono-id text-xs text-muted-foreground mt-0.5">#{index + 1}</span>
          <h3 className="text-sm font-medium text-foreground leading-snug">{finding.headline || "Untitled lead"}</h3>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {finding.evidence_tier && <StatusChip map={TIER} value={finding.evidence_tier} />}
          {finding.confidence && <StatusChip map={CONFIDENCE} value={finding.confidence} />}
        </div>
      </div>

      {finding.summary && <p className="text-sm text-muted-foreground leading-relaxed">{finding.summary}</p>}

      {Array.isArray(finding.sources) && finding.sources.length > 0 && (
        <div className="pt-1 space-y-1 border-t border-border/60">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70 pt-2">Sources</div>
          {finding.sources.map((s, i) => (
            <a
              key={i}
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-xs text-blue-300 hover:text-blue-200 hover:underline"
            >
              <ExternalLink className="h-3 w-3 shrink-0" />
              <span className="truncate">{s.title || s.url}</span>
            </a>
          ))}
        </div>
      )}

      {finding.municipality && (
        <div className="text-[11px] text-muted-foreground">Location: {finding.municipality}</div>
      )}
    </Card>
  );
}