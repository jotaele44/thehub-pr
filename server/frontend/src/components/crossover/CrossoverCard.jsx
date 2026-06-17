import React from "react";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import { TIER } from "@/lib/chips";
import {
  MODULE_CHIP, CROSSOVER_STATUS_CHIP, BAND_CHIP, TYPE_CHIP,
} from "@/lib/crossover-config";
import { ArrowLeftRight, AlertTriangle, CheckCircle2, FileWarning, ExternalLink } from "lucide-react";

function Side({ module, label, id }) {
  return (
    <div className="flex-1 min-w-0 rounded-lg border border-border bg-secondary/40 p-3">
      <StatusChip map={MODULE_CHIP} value={module} className="mb-2" />
      <div className="text-sm font-medium text-foreground truncate" title={label}>{label}</div>
      {id && <IdCode className="block mt-0.5">{id}</IdCode>}
    </div>
  );
}

export default function CrossoverCard({ c }) {
  const verified = c.status === "Verified";
  const contradicted = c.status === "Contradicted" || c.status === "Rejected";
  const noSource = !(c.source_ids?.length);

  return (
    <div className="rounded-xl border border-border bg-card p-4 space-y-3">
      {/* Side-by-side linked records */}
      <div className="flex items-stretch gap-2">
        <Side module={c.source_module} label={c.source_label} id={c.source_record_id} />
        <div className="flex items-center text-muted-foreground"><ArrowLeftRight className="h-4 w-4" /></div>
        <Side module={c.target_module} label={c.target_label} id={c.target_record_id} />
      </div>

      {/* Chips row — status, band, type, tier, verification */}
      <div className="flex flex-wrap items-center gap-1.5">
        <StatusChip map={CROSSOVER_STATUS_CHIP} value={c.status} />
        <StatusChip map={BAND_CHIP} value={c.confidence_band} />
        <StatusChip map={TYPE_CHIP} value={c.correlation_type} />
        {c.evidence_tier && <StatusChip map={TIER} value={c.evidence_tier} />}
        <span className="text-xs font-mono-id text-muted-foreground">score {c.confidence_score}</span>
        {verified
          ? <span className="inline-flex items-center gap-1 text-xs text-emerald-300"><CheckCircle2 className="h-3 w-3" /> review-verified linkage</span>
          : <span className="text-xs text-yellow-300/80">candidate · not verified</span>}
        {c.related_modules?.length >= 3 && (
          <span className="text-xs text-violet-300">+{c.related_modules.length} modules</span>
        )}
      </div>

      {/* Evidence tier meaning resolved from the EvidenceStandards ledger */}
      {c.tier_meaning?.definition && (
        <p className="text-xs text-muted-foreground">
          <span className="font-mono-id text-foreground/80">{c.evidence_tier}</span>
          {c.tier_meaning.label ? ` ${c.tier_meaning.label}` : ""} — {c.tier_meaning.definition}
        </p>
      )}

      {/* Rationale always visible (required for verified rows, shown for all) */}
      {c.rationale && <p className="text-sm text-foreground/90">{c.rationale}</p>}

      {/* Matching criteria / provenance */}
      {c.matching_criteria?.length > 0 && (
        <div className="text-xs text-muted-foreground">
          Basis: {c.matching_criteria.join(", ")} · from {c.created_from}
        </div>
      )}

      {/* Sources — resolved to UnifiedSources with evidence tier where the record exists */}
      <div className="flex flex-wrap items-center gap-1.5 text-xs">
        {c.resolved_sources?.length
          ? c.resolved_sources.map((s) => (
              s.title ? (
                s.url ? (
                  <a key={s.id} href={s.url} target="_blank" rel="noreferrer" title={s.title}
                    className="inline-flex items-center gap-1 rounded-md border border-blue-500/30 bg-blue-500/10 px-1.5 py-0.5 text-blue-300 max-w-[14rem]">
                    <span className="truncate">{s.title}</span>{s.tier && <span className="font-mono-id">{s.tier}</span>}<ExternalLink className="h-3 w-3 shrink-0" />
                  </a>
                ) : (
                  <span key={s.id} title={s.title}
                    className="inline-flex items-center gap-1 rounded-md border border-border bg-secondary/40 px-1.5 py-0.5 max-w-[14rem]">
                    <span className="truncate">{s.title}</span>{s.tier && <span className="font-mono-id text-muted-foreground">{s.tier}</span>}
                  </span>
                )
              ) : (
                <span key={s.id} className="inline-flex items-center gap-1 text-yellow-300/80" title="Referenced source_id not found in UnifiedSources">
                  <FileWarning className="h-3 w-3" /><IdCode>{s.id}</IdCode> unresolved
                </span>
              )
            ))
          : <span className="inline-flex items-center gap-1 text-yellow-300/80"><FileWarning className="h-3 w-3" /> no source reference</span>}
      </div>

      {/* Contradiction / caveat — preserved, never deleted */}
      {(contradicted || c.contradiction_notes) && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-2 text-xs text-amber-200">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
          <span>{c.contradiction_notes || "Marked contradicted/rejected during review. Caveat preserved."}</span>
        </div>
      )}
    </div>
  );
}