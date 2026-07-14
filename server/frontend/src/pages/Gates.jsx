import React, { useState } from "react";
import { useEntityData } from "@/hooks/useEntityData";
import { useTableFilter } from "@/hooks/useTableFilter";
import PageHeader from "@/components/shared/PageHeader";
import FilterBar from "@/components/shared/FilterBar";
import SearchableTable from "@/components/shared/SearchableTable";
import StatusChip from "@/components/shared/StatusChip";
import RecordSheet from "@/components/shared/RecordSheet";
import { Button } from "@/components/ui/button";
import { ShieldCheck, Plus, Lock } from "lucide-react";
import { GATE_STATUS } from "@/lib/chips";
import { GATE_NAMES } from "@/lib/federation";

const STATUSES = ["NotStarted", "InProgress", "Passed", "Failed", "Blocked"];

export default function Gates() {
  const { rows, create, update, saving } = useEntityData("ValidationGates");
  const { rows: programs } = useEntityData("Programs");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const FIELDS = [
    { key: "gate_id", label: "Gate ID", required: true, placeholder: "gate-001" },
    { key: "program_id", label: "Program", type: "select", options: programs.map((p) => p.program_id), required: true },
    { key: "gate_name", label: "Gate Name", type: "select", options: GATE_NAMES, required: true },
    { key: "status", label: "Status", type: "select", options: STATUSES, required: true },
    { key: "blocking", label: "Blocking (true/false)", type: "select", options: ["true", "false"], required: true },
    { key: "requirement", label: "Requirement", type: "textarea", required: true },
    { key: "review_notes", label: "Review Notes", type: "textarea" },
    { key: "reviewed_at", label: "Reviewed At", type: "date" },
  ];

  const { filtered, filterBarProps } = useTableFilter(rows, ["gate_name", "gate_id", "requirement"], [
    { key: "status", label: "Status", options: STATUSES },
  ]);

  const openNew = () => { setEditing(null); setOpen(true); };
  const openEdit = (row) => { setEditing({ ...row, blocking: String(row.blocking) }); setOpen(true); };
  const handleSave = async (data) => {
    const payload = { ...data, blocking: data.blocking === "true" || data.blocking === true };
    if (editing) await update({ id: editing.id, data: payload });
    else await create(payload);
    setOpen(false);
  };

  const blockingOpen = rows.filter((g) => g.blocking && g.status !== "Passed").length;

  const columns = [
    { key: "gate_name", label: "Gate", render: (r) => <span className="font-medium">{r.gate_name}</span> },
    { key: "program_id", label: "Program", render: (r) => <span className="text-muted-foreground font-mono-id text-xs">{r.program_id}</span> },
    { key: "blocking", label: "Blocking", render: (r) => r.blocking ? <span className="inline-flex items-center gap-1 text-xs text-status-warning-fg"><Lock className="h-3 w-3" />Yes</span> : <span className="text-xs text-muted-foreground">No</span> },
    { key: "status", label: "Status", render: (r) => <StatusChip map={GATE_STATUS} value={r.status} /> },
    { key: "reviewed_at", label: "Reviewed" },
  ];

  return (
    <div>
      <PageHeader
        icon={ShieldCheck}
        title="Validation Gates"
        description="Production-readiness checkpoints. GitHub sync stays blocked until every blocking gate is marked Passed."
        actions={<Button onClick={openNew}><Plus className="h-4 w-4 mr-2" />New Gate</Button>}
      />
      {blockingOpen > 0 && (
        <div className="mb-4 rounded-lg border border-status-warning/30 bg-status-warning/10 px-4 py-3 text-sm text-status-warning-fg flex items-center gap-2">
          <Lock className="h-4 w-4" />
          {blockingOpen} blocking gate{blockingOpen > 1 ? "s" : ""} not yet passed — repository sync remains blocked.
        </div>
      )}
      <FilterBar {...filterBarProps} searchPlaceholder="Search gates…" />
      <SearchableTable columns={columns} rows={filtered} onRowClick={openEdit} emptyTitle="No gates" emptyDescription="Define validation gates for your programs." />
      <RecordSheet open={open} onOpenChange={setOpen} title={editing ? "Edit Gate" : "New Gate"} fields={FIELDS} initial={editing} onSave={handleSave} saving={saving} />
    </div>
  );
}