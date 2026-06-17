import React, { useState } from "react";
import { useEntityData } from "@/hooks/useEntityData";
import { useTableFilter } from "@/hooks/useTableFilter";
import PageHeader from "@/components/shared/PageHeader";
import FilterBar from "@/components/shared/FilterBar";
import SearchableTable from "@/components/shared/SearchableTable";
import StatusChip from "@/components/shared/StatusChip";
import RecordSheet from "@/components/shared/RecordSheet";
import { Button } from "@/components/ui/button";
import { Plug, Plus } from "lucide-react";
import { INTEGRATION_STATUS } from "@/lib/chips";

const NAMES = ["Federation", "GitHub", "CSVExport", "GeoJSONExport", "GoogleDrive", "ManualImport"];
const STATUSES = ["NotConnected", "Blocked", "Ready", "Connected", "Error"];

export default function Integrations() {
  const { rows, create, update, saving } = useEntityData("IntegrationStatus");
  const { rows: programs } = useEntityData("Programs");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const FIELDS = [
    { key: "integration_id", label: "Integration ID", required: true, placeholder: "int-001" },
    { key: "program_id", label: "Program", type: "select", options: programs.map((p) => p.program_id), required: true },
    { key: "integration_name", label: "Integration", type: "select", options: NAMES, required: true },
    { key: "status", label: "Status", type: "select", options: STATUSES, required: true },
    { key: "last_checked", label: "Last Checked", type: "date" },
    { key: "blocking_reason", label: "Blocking Reason", type: "textarea" },
    { key: "next_action", label: "Next Action", type: "textarea" },
  ];

  const { filtered, filterBarProps } = useTableFilter(rows, ["integration_id", "next_action"], [
    { key: "integration_name", label: "Integration", options: NAMES },
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
    { key: "integration_name", label: "Integration", render: (r) => <span className="font-medium">{r.integration_name}</span> },
    { key: "program_id", label: "Program", render: (r) => <span className="text-muted-foreground font-mono-id text-xs">{r.program_id}</span> },
    { key: "status", label: "Status", render: (r) => <StatusChip map={INTEGRATION_STATUS} value={r.status} /> },
    { key: "blocking_reason", label: "Blocking Reason", sortable: false, render: (r) => <span className="text-xs text-muted-foreground line-clamp-1">{r.blocking_reason || "—"}</span> },
    { key: "next_action", label: "Next Action", sortable: false, render: (r) => <span className="text-xs text-muted-foreground line-clamp-1">{r.next_action || "—"}</span> },
    { key: "last_checked", label: "Checked" },
  ];

  return (
    <div>
      <PageHeader
        icon={Plug}
        title="Integrations"
        description="Connection state for each program. GitHub and export channels stay blocked until validation gates clear them."
        actions={<Button onClick={openNew}><Plus className="h-4 w-4 mr-2" />New Integration</Button>}
      />
      <FilterBar {...filterBarProps} searchPlaceholder="Search integrations…" />
      <SearchableTable columns={columns} rows={filtered} onRowClick={openEdit} emptyTitle="No integrations" emptyDescription="Track integration connection state per program." />
      <RecordSheet open={open} onOpenChange={setOpen} title={editing ? "Edit Integration" : "New Integration"} fields={FIELDS} initial={editing} onSave={handleSave} saving={saving} />
    </div>
  );
}