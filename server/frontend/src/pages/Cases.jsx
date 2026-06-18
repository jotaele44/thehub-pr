import React, { useState } from "react";
import { useEntityData } from "@/hooks/useEntityData";
import { useTableFilter } from "@/hooks/useTableFilter";
import PageHeader from "@/components/shared/PageHeader";
import FilterBar from "@/components/shared/FilterBar";
import SearchableTable from "@/components/shared/SearchableTable";
import StatusChip from "@/components/shared/StatusChip";
import RecordSheet from "@/components/shared/RecordSheet";
import IdCode from "@/components/shared/IdCode";
import CaseGateTracker from "@/components/cases/CaseGateTracker";
import BriefTemplateDialog from "@/components/cases/BriefTemplateDialog";
import { Button } from "@/components/ui/button";
import { FileStack, Plus, FileDown } from "lucide-react";
import { CASE_STATUS, CONFIDENCE, SENSITIVITY } from "@/lib/chips";
import { REGIONS } from "@/lib/federation";
import { getCaseGateProgress } from "@/lib/case-gate-progress";

const TYPES = ["UAP", "Infrastructure", "Contract", "Airspace", "Network", "Control", "Other"];
const STATUSES = ["New", "Reviewing", "Corroborated", "Contradicted", "Archived"];

export default function Cases() {
  const { rows, create, update, saving } = useEntityData("UnifiedCases");
  const { rows: programs } = useEntityData("Programs");
  const { rows: sources } = useEntityData("UnifiedSources");
  const { rows: anomalies } = useEntityData("AnomalyFlags");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [briefCase, setBriefCase] = useState(null);

  const FIELDS = [
    { key: "case_id", label: "Case ID", required: true, placeholder: "case-001" },
    { key: "case_code", label: "Case Code", required: true, placeholder: "UAP-2024-001" },
    { key: "program_id", label: "Program", type: "select", options: programs.map((p) => p.program_id), required: true },
    { key: "title", label: "Title", required: true, full: true },
    { key: "case_type", label: "Type", type: "select", options: TYPES, required: true },
    { key: "status", label: "Status", type: "select", options: STATUSES, required: true },
    { key: "event_date", label: "Event Date", type: "date" },
    { key: "date_precision", label: "Date Precision", type: "select", options: ["Exact", "Month", "Year", "Undated"], required: true },
    { key: "municipality", label: "Municipality" },
    { key: "region", label: "Region", type: "select", options: REGIONS },
    { key: "latitude", label: "Latitude", type: "number" },
    { key: "longitude", label: "Longitude", type: "number" },
    { key: "confidence", label: "Confidence", type: "select", options: ["Low", "Medium", "High"], required: true },
    { key: "sensitivity", label: "Sensitivity", type: "select", options: ["Public", "Internal", "Restricted"], required: true },
    { key: "summary_public", label: "Public Summary", type: "textarea", required: true },
  ];

  const { filtered, filterBarProps } = useTableFilter(rows, ["title", "case_code", "case_id", "municipality"], [
    { key: "case_type", label: "Type", options: TYPES },
    { key: "status", label: "Status", options: STATUSES },
    { key: "confidence", label: "Confidence", options: ["Low", "Medium", "High"] },
  ]);

  const openNew = () => { setEditing(null); setOpen(true); };
  const openEdit = (row) => { setEditing(row); setOpen(true); };
  const handleSave = async (data) => {
    if (editing) await update({ id: editing.id, data });
    else await create(data);
    setOpen(false);
  };

  const columns = [
    { key: "case_code", label: "Code", render: (r) => <IdCode>{r.case_code}</IdCode> },
    { key: "title", label: "Title", render: (r) => <span className="font-medium">{r.title}</span> },
    { key: "case_type", label: "Type", render: (r) => <span className="text-muted-foreground">{r.case_type}</span> },
    { key: "municipality", label: "Municipality" },
    { key: "confidence", label: "Confidence", render: (r) => <StatusChip map={CONFIDENCE} value={r.confidence} /> },
    { key: "status", label: "Status", render: (r) => <StatusChip map={CASE_STATUS} value={r.status} /> },
    { key: "validation_progress", label: "Validation Progress", render: (r) => <CaseGateTracker progress={getCaseGateProgress(r, sources)} compact /> },
    { key: "sensitivity", label: "Sensitivity", render: (r) => <StatusChip map={SENSITIVITY} value={r.sensitivity} /> },
    {
      key: "brief", label: "Brief", sortable: false, render: (r) => (
        <Button
          variant="outline"
          size="sm"
          onClick={(e) => { e.stopPropagation(); setBriefCase(r); }}
        >
          <FileDown className="h-3.5 w-3.5 mr-1.5" />PDF
        </Button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        icon={FileStack}
        title="Unified Cases"
        description="Cross-module case ledger. Public summaries and analytical metadata only — no raw evidence stored."
        actions={<Button onClick={openNew}><Plus className="h-4 w-4 mr-2" />New Case</Button>}
      />
      <FilterBar {...filterBarProps} searchPlaceholder="Search cases…" />
      <SearchableTable columns={columns} rows={filtered} onRowClick={openEdit} emptyTitle="No cases" emptyDescription="Add a unified case to start tracking." />
      <RecordSheet open={open} onOpenChange={setOpen} title={editing ? "Edit Case" : "New Case"} fields={FIELDS} initial={editing} onSave={handleSave} saving={saving} />
      <BriefTemplateDialog open={!!briefCase} onOpenChange={(v) => !v && setBriefCase(null)} caseRow={briefCase} sources={sources} anomalies={anomalies} />
    </div>
  );
}