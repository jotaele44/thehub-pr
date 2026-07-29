import React, { useState } from "react";
import { useEntityData } from "@/hooks/useEntityData";
import { useTableFilter } from "@/hooks/useTableFilter";
import FilterBar from "@/components/shared/FilterBar";
import SearchableTable from "@/components/shared/SearchableTable";
import RecordSheet from "@/components/shared/RecordSheet";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";

// Self-contained CRUD ledger for one entity. Reused by module tabs.
// props: entityName, fields, columns, searchKeys, filterDefs, addLabel, emptyTitle, emptyDescription, transformIn?, transformOut?, rowFilter?, readOnly?
//
// `rowFilter` narrows the collection before filtering — needed for collections that
// span producers (e.g. GovernanceAlerts holds every module's federation alerts, but a
// module tab must show only its own). `readOnly` hides the create/edit affordances for
// collections that are projections of a federation export rather than hub-authored
// records: editing one would be silently overwritten by the next `hub ingest`.
export default function EntityLedger({
  entityName, fields, columns, searchKeys, filterDefs = [],
  addLabel = "New Record", emptyTitle = "No records", emptyDescription,
  transformIn, transformOut, searchPlaceholder = "Search…",
  rowFilter, readOnly = false,
}) {
  const { rows, create, update, saving } = useEntityData(entityName);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const scoped = React.useMemo(
    () => (rowFilter ? rows.filter(rowFilter) : rows),
    [rows, rowFilter],
  );
  const { filtered, filterBarProps } = useTableFilter(scoped, searchKeys, filterDefs);

  const openNew = () => { setEditing(null); setOpen(true); };
  const openEdit = (row) => { setEditing(transformIn ? transformIn(row) : row); setOpen(true); };
  const handleSave = async (data) => {
    const payload = transformOut ? transformOut(data) : data;
    if (editing) await update({ id: editing.id, data: payload });
    else await create(payload);
    setOpen(false);
  };

  return (
    <div>
      {!readOnly && (
        <div className="flex justify-end mb-3">
          <Button size="sm" onClick={openNew}><Plus className="h-4 w-4 mr-2" />{addLabel}</Button>
        </div>
      )}
      <FilterBar {...filterBarProps} searchPlaceholder={searchPlaceholder} />
      <SearchableTable columns={columns} rows={filtered} onRowClick={readOnly ? undefined : openEdit} emptyTitle={emptyTitle} emptyDescription={emptyDescription} />
      {!readOnly && (
        <RecordSheet open={open} onOpenChange={setOpen} title={editing ? `Edit ${addLabel.replace("New ", "")}` : addLabel} fields={fields} initial={editing} onSave={handleSave} saving={saving} />
      )}
    </div>
  );
}