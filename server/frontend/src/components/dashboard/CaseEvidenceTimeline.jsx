import React, { useMemo, useState } from "react";
import { useEntityData } from "@/hooks/useEntityData";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import EmptyState from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { TIER, VERIFICATION } from "@/lib/chips";
import { History, ExternalLink, CalendarClock } from "lucide-react";

const FILTERS = [
  { key: "all", label: "All" },
  { key: "confirmed", label: "Confirmed" },
  { key: "pending", label: "Pending" },
];

const isConfirmed = (s) => s.verification_status === "Verified";
const isPending = (s) => s.verification_status === "Unreviewed" || s.verification_status === "Disputed";

// Best available chronological key for a source: publication, else retrieved.
const sortDate = (s) => s.publication_date || s.retrieved_date || "";

export default function CaseEvidenceTimeline() {
  const { rows: cases } = useEntityData("UnifiedCases");
  const { rows: sources } = useEntityData("UnifiedSources");

  const [caseId, setCaseId] = useState("");
  const [filter, setFilter] = useState("all");

  // Default to the first case once data loads.
  const selectedCaseId = caseId || cases[0]?.case_id || "";
  const selectedCase = cases.find((c) => c.case_id === selectedCaseId);

  const timeline = useMemo(() => {
    const linked = sources.filter((s) => s.linked_case_id === selectedCaseId);
    const filtered = linked.filter((s) => {
      if (filter === "confirmed") return isConfirmed(s);
      if (filter === "pending") return isPending(s);
      return true;
    });
    return filtered.sort((a, b) => sortDate(a).localeCompare(sortDate(b)));
  }, [sources, selectedCaseId, filter]);

  const confirmedCount = sources.filter((s) => s.linked_case_id === selectedCaseId && isConfirmed(s)).length;
  const pendingCount = sources.filter((s) => s.linked_case_id === selectedCaseId && isPending(s)).length;

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="flex items-center gap-2 mr-auto">
          <History className="h-4 w-4 text-status-info-fg" />
          <h3 className="text-sm font-semibold">Case Evidence Timeline</h3>
        </div>

        <Select value={selectedCaseId} onValueChange={setCaseId}>
          <SelectTrigger className="w-[16rem] h-8 text-xs">
            <SelectValue placeholder="Select a case" />
          </SelectTrigger>
          <SelectContent>
            {cases.map((c) => (
              <SelectItem key={c.id} value={c.case_id}>
                <span className="font-mono-id mr-1">{c.case_code}</span> {c.title}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="flex rounded-lg border border-border overflow-hidden">
          {FILTERS.map((f) => (
            <Button
              key={f.key}
              size="sm"
              variant={filter === f.key ? "secondary" : "ghost"}
              className="h-8 rounded-none text-xs px-3"
              onClick={() => setFilter(f.key)}
            >
              {f.label}
              {f.key === "confirmed" && <span className="ml-1 text-status-success-fg">{confirmedCount}</span>}
              {f.key === "pending" && <span className="ml-1 text-status-warning-fg">{pendingCount}</span>}
            </Button>
          ))}
        </div>
      </div>

      {selectedCase && (
        <p className="text-xs text-muted-foreground mb-4">
          Chronological evidence for <span className="font-mono-id text-foreground/80">{selectedCase.case_code}</span> — {selectedCase.title}. Ordered by publication date (falls back to retrieved date).
        </p>
      )}

      {!timeline.length ? (
        <EmptyState
          icon={CalendarClock}
          title="No evidence on this timeline"
          description={cases.length ? "No sources match the current case and filter." : "No cases available yet."}
        />
      ) : (
        <ol className="relative border-l border-border ml-2 space-y-5">
          {timeline.map((s) => (
            <li key={s.id} className="ml-5">
              <span className="absolute -left-[7px] mt-1 h-3 w-3 rounded-full border-2 border-card bg-status-info" />
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <span className="text-xs font-mono-id text-foreground/80">
                  {sortDate(s) || "Undated"}
                </span>
                {s.evidence_tier && <StatusChip map={TIER} value={s.evidence_tier} />}
                <StatusChip map={VERIFICATION} value={s.verification_status} />
                <span className="text-xs text-muted-foreground">{s.source_type}</span>
              </div>
              <div className="text-sm font-medium text-foreground">{s.title}</div>
              {s.summary && <p className="text-xs text-muted-foreground mt-0.5">{s.summary}</p>}
              <div className="flex items-center gap-3 mt-1 text-xs">
                <IdCode>{s.source_id}</IdCode>
                {s.publisher && <span className="text-muted-foreground">{s.publisher}</span>}
                {s.url && (
                  <a href={s.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-status-info-fg hover:underline">
                    Source <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}