import React, { useState } from "react";
import { useEntityData } from "@/hooks/useEntityData";
import { useTableFilter } from "@/hooks/useTableFilter";
import FilterBar from "@/components/shared/FilterBar";
import SearchableTable from "@/components/shared/SearchableTable";
import RecordSheet from "@/components/shared/RecordSheet";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";

// Self-contained CRUD ledger for one entity. Reused by module tabs.
// props: entityName, fields, columns, searchKeys, filterDefs, addLabel, emptyTitle, emptyDescription, transformIn?, transformOut?
export default function EntityLedger({
  entityName, fields, columns, searchKeys, filterDefs = [],
  addLabel = "New Record", emptyTitle = "No records", emptyDescription,
  transformIn, transformOut, searchPlaceholder = "Search…",
}) {
  const { rows, create, update, saving } = useEntityData(entityName);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const { filtered, filterBarProps } = useTableFilter(rows, searchKeys, filterDefs);

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
      <div className="flex justify-end mb-3">
        <Button size="sm" onClick={openNew}><Plus className="h-4 w-4 mr-2" />{addLabel}</Button>
      </div>
      <FilterBar {...filterBarProps} searchPlaceholder={searchPlaceholder} />
      <SearchableTable columns={columns} rows={filtered} onRowClick={openEdit} emptyTitle={emptyTitle} emptyDescription={emptyDescription} />
      <RecordSheet open={open} onOpenChange={setOpen} title={editing ? `Edit ${addLabel.replace("New ", "")}` : addLabel} fields={fields} initial={editing} onSave={handleSave} saving={saving} />
    </div>
  );
}