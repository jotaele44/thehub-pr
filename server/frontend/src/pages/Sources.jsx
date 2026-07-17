import React, { useState } from "react";
import { useEntityData } from "@/hooks/useEntityData";
import { useTableFilter } from "@/hooks/useTableFilter";
import PageHeader from "@/components/shared/PageHeader";
import FilterBar from "@/components/shared/FilterBar";
import SearchableTable from "@/components/shared/SearchableTable";
import StatusChip from "@/components/shared/StatusChip";
import RecordSheet from "@/components/shared/RecordSheet";
import IdCode from "@/components/shared/IdCode";
import { Button } from "@/components/ui/button";
import { BookOpen, Plus, ExternalLink } from "lucide-react";
import { TIER, VERIFICATION, REVIEW_STATUS } from "@/lib/chips";

const TYPES = ["Government", "Technical", "Operational", "Eyewitness", "News", "Academic", "Secondary", "Other"];
const TIERS = ["T1", "T2", "T3", "T4"];

export default function Sources() {
  const { rows, create, update, saving } = useEntityData("UnifiedSources");
  const { rows: programs } = useEntityData("Programs");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const FIELDS = [
    { key: "source_id", label: "Source ID", required: true, placeholder: "src-001" },
    { key: "program_id", label: "Program", type: "select", options: programs.map((p) => p.program_id), required: true },
    { key: "title", label: "Title", required: true, full: true },
    { key: "source_type", label: "Type", type: "select", options: TYPES, required: true },
    { key: "evidence_tier", label: "Evidence Tier", type: "select", options: TIERS, required: true },
    { key: "publisher", label: "Publisher" },
    { key: "publication_date", label: "Publication Date", type: "date" },
    { key: "retrieved_date", label: "Retrieved Date", type: "date" },
    { key: "url", label: "URL", full: true },
    { key: "archive_ref", label: "Archive Ref" },
    { key: "reliability", label: "Reliability", type: "select", options: ["Low", "Medium", "High", "Unknown"], required: true },
    { key: "verification_status", label: "Verification", type: "select", options: ["Unreviewed", "Verified", "Disputed", "Rejected"], required: true },
    { key: "sensitivity", label: "Sensitivity", type: "select", options: ["Public", "Internal", "Restricted"], required: true },
    { key: "summary", label: "Summary", type: "textarea", required: true },
  ];

  const { filtered, filterBarProps } = useTableFilter(rows, ["title", "source_id", "publisher"], [
    { key: "source_type", label: "Type", options: TYPES },
    { key: "evidence_tier", label: "Tier", options: TIERS },
    { key: "verification_status", label: "Verification", options: ["Unreviewed", "Verified", "Disputed", "Rejected"] },
  ]);

  const openNew = () => { setEditing(null); setOpen(true); };
  const openEdit = (row) => { setEditing(row); setOpen(true); };
  const handleSave = async (data) => {
    if (editing) await update({ id: editing.id, data });
    else await create(data);
    setOpen(false);
  };

  const columns = [
    { key: "source_id", label: "ID", render: (r) => <IdCode>{r.source_id}</IdCode> },
    { key: "title", label: "Title", render: (r) => <span className="font-medium">{r.title}</span> },
    { key: "source_type", label: "Type", render: (r) => <span className="text-muted-foreground">{r.source_type}</span> },
    { key: "evidence_tier", label: "Tier", render: (r) => <StatusChip map={TIER} value={r.evidence_tier} /> },
    { key: "reliability", label: "Reliability", render: (r) => <StatusChip map={REVIEW_STATUS} value={r.reliability} /> },
    { key: "verification_status", label: "Verification", render: (r) => <StatusChip map={VERIFICATION} value={r.verification_status} /> },
    { key: "url", label: "Link", sortable: false, render: (r) => r.url ? <a href={r.url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} className="text-status-info-fg inline-flex"><ExternalLink className="h-4 w-4" /></a> : <span className="text-muted-foreground">—</span> },
  ];

  return (
    <div>
      <PageHeader
        icon={BookOpen}
        title="Unified Sources"
        description="Source registry with evidence-tier classification (T1–T4) and verification tracking across all modules."
        actions={<Button onClick={openNew}><Plus className="h-4 w-4 mr-2" />New Source</Button>}
      />
      <FilterBar {...filterBarProps} searchPlaceholder="Search sources…" />
      <SearchableTable columns={columns} rows={filtered} onRowClick={openEdit} emptyTitle="No sources" emptyDescription="Add a source reference to begin." />
      <RecordSheet open={open} onOpenChange={setOpen} title={editing ? "Edit Source" : "New Source"} fields={FIELDS} initial={editing} onSave={handleSave} saving={saving} />
    </div>
  );
}