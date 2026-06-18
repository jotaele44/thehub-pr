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
import { FolderKanban, Plus } from "lucide-react";
import { PROGRAM_STATUS, GITHUB_STATUS, FEDERATION_STATUS, SENSITIVITY } from "@/lib/chips";

const DOMAINS = ["ControlPlane", "NetworkGraph", "UAP", "Infrastructure", "Contracts", "Airspace"];
const STATUSES = ["Planned", "Active", "Paused", "Archived"];

const FIELDS = [
  { key: "program_id", label: "Program ID", required: true, placeholder: "prog-001" },
  { key: "name", label: "Name", required: true },
  { key: "old_name", label: "Legacy Name" },
  { key: "repo_name", label: "Repo Name" },
  { key: "domain", label: "Domain", type: "select", options: DOMAINS, required: true },
  { key: "status", label: "Status", type: "select", options: STATUSES, required: true },
  { key: "owner", label: "Owner" },
  { key: "lead_vector", label: "Lead Vector" },
  { key: "github_sync_status", label: "GitHub Sync", type: "select", options: ["NotConnected", "Blocked", "Ready", "Connected"], required: true },
  { key: "federation_status", label: "Federation Status", type: "select", options: ["Draft", "Reviewing", "Stable", "NeedsRevision"], required: true },
  { key: "sensitivity_default", label: "Default Sensitivity", type: "select", options: ["Public", "Internal", "Restricted"], required: true },
  { key: "description", label: "Description", type: "textarea" },
];

export default function Programs() {
  const { rows, create, update, saving } = useEntityData("Programs", "program_id");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const { filtered, filterBarProps } = useTableFilter(rows, ["name", "program_id", "owner", "old_name"], [
    { key: "domain", label: "Domain", options: DOMAINS },
    { key: "status", label: "Status", options: STATUSES },
  ]);

  const openNew = () => { setEditing(null); setOpen(true); };
  const openEdit = (row) => { setEditing(row); setOpen(true); };
  const handleSave = async (data) => {
    if (editing) await update({ id: editing.id, data });
    else await create(data);
    setOpen(false);
  };

  const columns = [
    { key: "program_id", label: "ID", render: (r) => <IdCode>{r.program_id}</IdCode> },
    { key: "name", label: "Name", render: (r) => <span className="font-medium">{r.name}</span> },
    { key: "domain", label: "Domain", render: (r) => <span className="text-muted-foreground">{r.domain}</span> },
    { key: "status", label: "Status", render: (r) => <StatusChip map={PROGRAM_STATUS} value={r.status} /> },
    { key: "federation_status", label: "Federation", render: (r) => <StatusChip map={FEDERATION_STATUS} value={r.federation_status} /> },
    { key: "github_sync_status", label: "GitHub", render: (r) => <StatusChip map={GITHUB_STATUS} value={r.github_sync_status} /> },
    { key: "sensitivity_default", label: "Sensitivity", render: (r) => <StatusChip map={SENSITIVITY} value={r.sensitivity_default} /> },
  ];

  return (
    <div>
      <PageHeader
        icon={FolderKanban}
        title="Programs"
        description="Federation program registry — each module and shared service tracked with standardized identity, status, and gated sync state."
        actions={<Button onClick={openNew}><Plus className="h-4 w-4 mr-2" />New Program</Button>}
      />
      <FilterBar {...filterBarProps} searchPlaceholder="Search programs…" />
      <SearchableTable columns={columns} rows={filtered} onRowClick={openEdit} emptyTitle="No programs" emptyDescription="Create your first federation program to begin." initialSort={{ key: "program_id", dir: "asc" }} />
      <RecordSheet open={open} onOpenChange={setOpen} title={editing ? "Edit Program" : "New Program"} fields={FIELDS} initial={editing} onSave={handleSave} saving={saving} />
    </div>
  );
}