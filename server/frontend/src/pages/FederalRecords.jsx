import React, { useMemo, useState } from "react";
import { useEntityData } from "@/hooks/useEntityData";
import PageHeader from "@/components/shared/PageHeader";
import SearchableTable from "@/components/shared/SearchableTable";
import IdCode from "@/components/shared/IdCode";
import { Button } from "@/components/ui/button";
import { FileSearch, ShieldAlert, Database, GitCompare, CheckCircle2 } from "lucide-react";

const VIEWS = [
  ["documents", "Documents"],
  ["releases", "Release timeline"],
  ["findings", "Findings queue"],
  ["redactions", "Redaction changes"],
  ["contradictions", "Contradictions"],
  ["gaps", "Data gaps"],
  ["corpus", "Corpus versions"],
];

function badge(value) {
  return <span className="rounded border px-2 py-1 text-xs font-medium">{value || "Unknown"}</span>;
}

export default function FederalRecords() {
  const [view, setView] = useState("documents");
  const { rows: documents } = useEntityData("FederalDocuments");
  const { rows: releases } = useEntityData("FederalDocumentReleases");
  const { rows: findings } = useEntityData("DocumentFindings");
  const { rows: candidates } = useEntityData("CaseActivityCandidates");
  const { rows: assessments } = useEntityData("CaseActivityAssessments");

  const rows = useMemo(() => {
    if (view === "documents") return documents;
    if (view === "releases") return releases;
    if (view === "findings") return findings;
    if (view === "redactions") return releases.filter((r) => ["LESS_REDACTED_VERSION", "MORE_REDACTED_VERSION"].includes(r.release_state));
    if (view === "contradictions") return assessments.filter((r) => r.classification === "CONTRADICTORY" || r.contradicts_case_claim);
    if (view === "gaps") return assessments.filter((r) => r.classification === "DATA_GAP");
    return releases.filter((r) => r.baseline_cutoff || r.delta_id);
  }, [view, documents, releases, findings, assessments]);

  const columns = useMemo(() => {
    if (view === "documents") return [
      { key: "document_id", label: "Document", render: (r) => <IdCode>{r.document_id}</IdCode> },
      { key: "title", label: "Title" },
      { key: "originating_agency", label: "Agency" },
      { key: "document_date_start", label: "Document date" },
      { key: "repository", label: "Repository" },
    ];
    if (view === "releases" || view === "redactions" || view === "corpus") return [
      { key: "release_id", label: "Release", render: (r) => <IdCode>{r.release_id}</IdCode> },
      { key: "release_state", label: "State", render: (r) => badge(r.release_state) },
      { key: "released_at", label: "Released" },
      { key: "first_observed_at", label: "Observed" },
      { key: "page_count", label: "Pages" },
      { key: "baseline_cutoff", label: "Baseline cutoff" },
    ];
    if (view === "findings") return [
      { key: "finding_id", label: "Finding", render: (r) => <IdCode>{r.finding_id}</IdCode> },
      { key: "finding_type", label: "Type", render: (r) => badge(r.finding_type) },
      { key: "context_summary", label: "Context" },
      { key: "page_start", label: "Page" },
      { key: "review_status", label: "Review", render: (r) => badge(r.review_status) },
    ];
    return [
      { key: "assessment_id", label: "Assessment", render: (r) => <IdCode>{r.assessment_id}</IdCode> },
      { key: "case_id", label: "Case" },
      { key: "classification", label: "Classification", render: (r) => badge(r.classification) },
      { key: "reasoning_summary", label: "Reasoning" },
      { key: "review_status", label: "Review", render: (r) => badge(r.review_status) },
    ];
  }, [view]);

  const pending = candidates.filter((r) => r.requires_human_review).length;
  return (
    <div>
      <PageHeader
        icon={FileSearch}
        title="Federal Records"
        description="Post-freeze release provenance, version changes, Puerto Rico findings, and OVNIS case-context review. Candidate links are never treated as conclusions."
      />
      <div className="mb-4 grid gap-3 md:grid-cols-4">
        <div className="rounded-lg border p-3"><Database className="mb-2 h-4 w-4" /><div className="text-2xl font-semibold">{documents.length}</div><div className="text-sm text-muted-foreground">Canonical documents</div></div>
        <div className="rounded-lg border p-3"><GitCompare className="mb-2 h-4 w-4" /><div className="text-2xl font-semibold">{releases.length}</div><div className="text-sm text-muted-foreground">Release versions</div></div>
        <div className="rounded-lg border p-3"><ShieldAlert className="mb-2 h-4 w-4" /><div className="text-2xl font-semibold">{pending}</div><div className="text-sm text-muted-foreground">Human-review candidates</div></div>
        <div className="rounded-lg border p-3"><CheckCircle2 className="mb-2 h-4 w-4" /><div className="text-2xl font-semibold">{assessments.length}</div><div className="text-sm text-muted-foreground">Adjudications</div></div>
      </div>
      <div className="mb-4 flex flex-wrap gap-2" aria-label="Federal records views">
        {VIEWS.map(([key, label]) => <Button key={key} variant={view === key ? "default" : "outline"} onClick={() => setView(key)}>{label}</Button>)}
      </div>
      <SearchableTable columns={columns} rows={rows} emptyTitle="No federal-record rows" emptyDescription="Ingest an adjudicated Centinelas package to populate this view." />
    </div>
  );
}
