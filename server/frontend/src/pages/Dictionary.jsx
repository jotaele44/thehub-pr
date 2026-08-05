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
import { BookA, Plus, ArrowRight } from "lucide-react";
import { DICTIONARY_STATUS } from "@/lib/chips";

const CATEGORIES = ["Agency", "Vendor", "Person", "Location", "Asset", "Program", "Acronym", "Alias", "Other"];
const MODULES = ["Hub", "Spiderweb-PR", "Ovnis-PR", "AguaYLuz-PR", "MoneySweep-PR", "Skywatcher-PR", "Centinelas-PR"];
const STATUSES = ["Proposed", "Approved", "Deprecated"];

export default function Dictionary() {
  const { rows, create, update, saving } = useEntityData("DictionaryTerms");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const FIELDS = [
    { key: "term_id", label: "Term ID", required: true, placeholder: "term-001" },
    { key: "raw_term", label: "Raw / Variant Term", required: true },
    { key: "normalized_term", label: "Normalized (Canonical) Term", required: true, full: true },
    { key: "category", label: "Category", type: "select", options: CATEGORIES },
    { key: "module", label: "Module", type: "select", options: MODULES },
    { key: "status", label: "Status", type: "select", options: STATUSES },
    { key: "definition", label: "Definition / Disambiguation", type: "textarea", full: true },
  ];

  const { filtered, filterBarProps } = useTableFilter(rows, ["raw_term", "normalized_term", "term_id", "definition"], [
    { key: "category", label: "Category", options: CATEGORIES },
    { key: "module", label: "Module", options: MODULES },
    { key: "status", label: "Status", options: STATUSES },
  ]);

  const openNew = () => { setEditing(null); setOpen(true); };
  const openEdit = (row) => { setEditing(row); setOpen(true); };
  const handleSave = async (data) => {
    if (editing) await update({ id: editing.id, data });
    else await create({ ...data, source_repo: "thehub-pr" });
    setOpen(false);
  };

  const columns = [
    { key: "term_id", label: "ID", render: (r) => <IdCode>{r.term_id}</IdCode> },
    {
      key: "raw_term", label: "Normalization", sortable: false, render: (r) => (
        <span className="flex items-center gap-2">
          <span className="text-muted-foreground">{r.raw_term}</span>
          <ArrowRight className="h-3.5 w-3.5 text-muted-foreground/60 shrink-0" />
          <span className="font-medium">{r.normalized_term}</span>
        </span>
      )
    },
    { key: "category", label: "Category", render: (r) => <span className="text-muted-foreground">{r.category || "—"}</span> },
    { key: "module", label: "Module", render: (r) => <span className="text-muted-foreground">{r.module || "—"}</span> },
    { key: "status", label: "Status", render: (r) => <StatusChip map={DICTIONARY_STATUS} value={r.status} /> },
  ];

  return (
    <div>
      <PageHeader
        icon={BookA}
        title="Normalization Dictionary"
        description="Map custom and variant terms (agencies, vendors, aliases, acronyms) to their canonical normalized forms for consistent cross-module analysis."
        actions={<Button onClick={openNew}><Plus className="h-4 w-4 mr-2" />New Term</Button>}
      />
      <FilterBar {...filterBarProps} searchPlaceholder="Search terms…" />
      <SearchableTable columns={columns} rows={filtered} onRowClick={openEdit} emptyTitle="No terms" emptyDescription="Add a term to start normalizing custom vocabulary." />
      <RecordSheet open={open} onOpenChange={setOpen} title={editing ? "Edit Term" : "New Term"} fields={FIELDS} initial={editing} onSave={handleSave} saving={saving} />
    </div>
  );
}