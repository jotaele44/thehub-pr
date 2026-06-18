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
import { Boxes, Plus } from "lucide-react";
import { GENERIC_STATUS } from "@/lib/chips";

const ROLES = ["ParentControlPlane", "ChildModule", "SharedService"];
const STATUSES = ["Draft", "Reviewing", "Stable", "Deprecated"];

export default function Manifest() {
  const { rows, create, update, saving } = useEntityData("FederationManifest");
  const { rows: programs } = useEntityData("Programs");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const FIELDS = [
    { key: "manifest_id", label: "Manifest ID", required: true, placeholder: "mf-001" },
    { key: "program_id", label: "Program", type: "select", options: programs.map((p) => p.program_id), required: true },
    { key: "module_role", label: "Module Role", type: "select", options: ROLES, required: true },
    { key: "schema_version", label: "Schema Version", required: true, placeholder: "1.0.0" },
    { key: "status", label: "Status", type: "select", options: STATUSES, required: true },
    { key: "notes", label: "Notes", type: "textarea" },
  ];

  const { filtered, filterBarProps } = useTableFilter(rows, ["manifest_id", "schema_version"], [
    { key: "module_role", label: "Role", options: ROLES },
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
    { key: "manifest_id", label: "ID", render: (r) => <IdCode>{r.manifest_id}</IdCode> },
    { key: "program_id", label: "Program", render: (r) => <span className="text-muted-foreground font-mono-id text-xs">{r.program_id}</span> },
    { key: "module_role", label: "Role", render: (r) => <span className="font-medium">{r.module_role}</span> },
    { key: "schema_version", label: "Schema", render: (r) => <IdCode>{r.schema_version}</IdCode> },
    { key: "status", label: "Status", render: (r) => <StatusChip map={GENERIC_STATUS} value={r.status} /> },
  ];

  return (
    <div>
      <PageHeader
        icon={Boxes}
        title="Federation Manifest"
        description="Per-program manifest declaring module role, schema version, and which shared entities and integrations are allowed or blocked."
        actions={<Button onClick={openNew}><Plus className="h-4 w-4 mr-2" />New Manifest</Button>}
      />
      <FilterBar {...filterBarProps} searchPlaceholder="Search manifests…" />
      <SearchableTable columns={columns} rows={filtered} onRowClick={openEdit} emptyTitle="No manifests" emptyDescription="Declare a manifest for each program." />
      <RecordSheet open={open} onOpenChange={setOpen} title={editing ? "Edit Manifest" : "New Manifest"} fields={FIELDS} initial={editing} onSave={handleSave} saving={saving} />
    </div>
  );
}