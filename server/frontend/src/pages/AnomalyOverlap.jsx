import React, { useMemo, useState } from "react";
import { useEntityData } from "@/hooks/useEntityData";
import PageHeader from "@/components/shared/PageHeader";
import EmptyState from "@/components/shared/EmptyState";
import OverlapGroup from "@/components/overlap/OverlapGroup";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { GitCompareArrows, Layers } from "lucide-react";
import { MODULE_OPTIONS, buildOverlaps } from "@/lib/anomaly-overlap";

export default function AnomalyOverlap() {
  const { rows: cases, isLoading } = useEntityData("UnifiedCases");
  const [moduleA, setModuleA] = useState("Ovnis-PR");
  const [moduleB, setModuleB] = useState("AguaYLuz-PR");

  const overlaps = useMemo(() => buildOverlaps(cases, moduleA, moduleB), [cases, moduleA, moduleB]);

  const ModuleSelect = ({ value, onChange, label }) => (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
        <SelectContent>
          {MODULE_OPTIONS.map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}
        </SelectContent>
      </Select>
    </div>
  );

  return (
    <div>
      <PageHeader
        icon={GitCompareArrows}
        title="Anomaly Overlap"
        description="Compare anomaly-flagged cases from two modules side-by-side where they share a municipality or region. Overlaps are leads for cross-module review — not confirmed correlations."
      />

      <div className="flex flex-wrap items-end gap-4 mb-6">
        <ModuleSelect value={moduleA} onChange={setModuleA} label="Module A" />
        <GitCompareArrows className="h-5 w-5 text-muted-foreground mb-2.5" />
        <ModuleSelect value={moduleB} onChange={setModuleB} label="Module B" />
        <div className="ml-auto flex items-center gap-2 text-sm text-muted-foreground mb-1">
          <Layers className="h-4 w-4" />
          {overlaps.length} shared {overlaps.length === 1 ? "location" : "locations"}
        </div>
      </div>

      {moduleA === moduleB ? (
        <EmptyState icon={GitCompareArrows} title="Pick two different modules" description="Select two distinct modules to compare their anomalies." />
      ) : isLoading ? (
        <EmptyState icon={Layers} title="Loading…" />
      ) : overlaps.length === 0 ? (
        <EmptyState icon={Layers} title="No geographic overlaps" description={`No anomalies from ${moduleA} and ${moduleB} currently share a municipality or region.`} />
      ) : (
        <div className="space-y-4">
          {overlaps.map((g) => (
            <OverlapGroup key={`${g.kind}:${g.label}`} group={g} moduleA={moduleA} moduleB={moduleB} />
          ))}
        </div>
      )}
    </div>
  );
}