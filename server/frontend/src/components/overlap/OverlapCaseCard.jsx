import React from "react";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import { CASE_STATUS, CONFIDENCE } from "@/lib/chips";

export default function OverlapCaseCard({ caseRow }) {
  return (
    <div className="rounded-md border border-border bg-card/60 p-2.5">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-medium text-foreground leading-snug">{caseRow.title}</span>
        <IdCode>{caseRow.case_code}</IdCode>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <span className="text-xs text-muted-foreground">{caseRow.case_type}</span>
        {caseRow.municipality && <span className="text-xs text-muted-foreground">· {caseRow.municipality}</span>}
        {caseRow.region && <span className="text-xs text-muted-foreground">· {caseRow.region}</span>}
        <StatusChip map={CONFIDENCE} value={caseRow.confidence} />
        <StatusChip map={CASE_STATUS} value={caseRow.status} />
      </div>
    </div>
  );
}