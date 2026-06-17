import React from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { MODULE_PAIRS, MODULE_SHORT, pairKey } from "@/lib/crossover-config";
import { X } from "lucide-react";

const TYPES = ["Geography", "Agency", "Vendor", "InfrastructureAdjacency", "LandDevelopment", "SourceEvidence", "Anomaly", "Temporal", "Contradiction", "Entity", "Graph", "Other"];

function FSelect({ value, onChange, placeholder, options }) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="h-8 w-auto min-w-[130px] text-xs"><SelectValue placeholder={placeholder} /></SelectTrigger>
      <SelectContent>
        {options.map((o) => <SelectItem key={o.value} value={o.value} className="text-xs">{o.label}</SelectItem>)}
      </SelectContent>
    </Select>
  );
}

export default function CrossoverFilters({ filters, setFilters, resetFilters, municipalities, agencies = [], vendorsList = [] }) {
  const set = (k) => (v) => setFilters((f) => ({ ...f, [k]: v }));

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Input
        value={filters.search}
        onChange={(e) => set("search")(e.target.value)}
        placeholder="Search records, rationale, municipality…"
        className="h-8 w-56 text-xs"
      />
      <FSelect value={filters.bucket} onChange={set("bucket")} placeholder="Status" options={[
        { value: "all", label: "All statuses" },
        { value: "verified", label: "Verified only" },
        { value: "pending", label: "Pending / candidate" },
        { value: "contradicted", label: "Contradicted / rejected" },
      ]} />
      <FSelect value={filters.band} onChange={set("band")} placeholder="Confidence" options={[
        { value: "all", label: "Any confidence" }, { value: "High", label: "High" }, { value: "Medium", label: "Medium" }, { value: "Low", label: "Low" },
      ]} />
      <FSelect value={filters.tier} onChange={set("tier")} placeholder="Evidence tier" options={[
        { value: "all", label: "Any tier" }, { value: "T1", label: "T1 Technical" }, { value: "T2", label: "T2 Operational" }, { value: "T3", label: "T3 Eyewitness" }, { value: "T4", label: "T4 Secondary" },
      ]} />
      <FSelect value={filters.type} onChange={set("type")} placeholder="Crossover type" options={[
        { value: "all", label: "Any type" }, ...TYPES.map((t) => ({ value: t, label: t })),
      ]} />
      <FSelect value={filters.pair} onChange={set("pair")} placeholder="Module pair" options={[
        { value: "all", label: "Any pair" },
        ...MODULE_PAIRS.map(([a, b]) => ({ value: pairKey(a, b), label: `${MODULE_SHORT[a]} ↔ ${MODULE_SHORT[b]}` })),
      ]} />
      {municipalities.length > 0 && (
        <FSelect value={filters.municipality} onChange={set("municipality")} placeholder="Municipality" options={[
          { value: "all", label: "Any municipality" }, ...municipalities.map((m) => ({ value: m, label: m })),
        ]} />
      )}
      {agencies.length > 0 && (
        <FSelect value={filters.agency} onChange={set("agency")} placeholder="Agency" options={[
          { value: "all", label: "Any agency" }, ...agencies.map((m) => ({ value: m, label: m })),
        ]} />
      )}
      {vendorsList.length > 0 && (
        <FSelect value={filters.vendor} onChange={set("vendor")} placeholder="Vendor" options={[
          { value: "all", label: "Any vendor" }, ...vendorsList.map((m) => ({ value: m, label: m })),
        ]} />
      )}
      <div className="flex items-center gap-1">
        <span className="text-[11px] text-muted-foreground">Date</span>
        <Input type="date" value={filters.dateFrom} onChange={(e) => set("dateFrom")(e.target.value)} className="h-8 w-[130px] text-xs" />
        <span className="text-[11px] text-muted-foreground">–</span>
        <Input type="date" value={filters.dateTo} onChange={(e) => set("dateTo")(e.target.value)} className="h-8 w-[130px] text-xs" />
      </div>
      <Button variant="ghost" size="sm" className="h-8 text-xs" onClick={resetFilters}>
        <X className="h-3 w-3 mr-1" /> Reset
      </Button>
    </div>
  );
}