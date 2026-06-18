import React from "react";
import { useQuery } from "@tanstack/react-query";
import { federation } from "@/api/federationClient";
import { Button } from "@/components/ui/button";
import { FileDown, MapPin, Loader2 } from "lucide-react";
import IdCode from "@/components/shared/IdCode";
import { exportLedgerCsv, exportLedgerGeoJson, geoCount } from "@/lib/export";

// One exportable ledger: shows live record count + CSV / GeoJSON actions.
export default function LedgerExportRow({ ledger, onExport }) {
  const { data: records = [], isLoading } = useQuery({
    queryKey: [ledger.entity, "export-count"],
    queryFn: () => federation.entities[ledger.entity].list(),
    initialData: [],
  });

  const total = records.length;
  const geo = ledger.geo ? geoCount(records) : 0;
  const fileNameBase = `${ledger.module.toLowerCase()}-${ledger.entity.toLowerCase()}`;

  const handleCsv = () => {
    const res = exportLedgerCsv(records, { columns: ledger.columns, fileNameBase, module: ledger.module });
    onExport?.({ ...res, ledger, format: "CSV", records });
  };
  const handleGeo = () => {
    const res = exportLedgerGeoJson(records, { fileNameBase, module: ledger.module });
    onExport?.({ ...res, ledger, format: "GeoJSON", records });
  };

  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-lg border border-border bg-card">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground">{ledger.label}</span>
          <IdCode>{ledger.entity}</IdCode>
        </div>
        <div className="text-xs text-muted-foreground mt-0.5">
          {ledger.module} · {isLoading ? "…" : total} record{total === 1 ? "" : "s"}
          {ledger.geo && <> · <span className="text-teal-300">{geo} mappable</span></>}
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <Button variant="outline" size="sm" className="h-8 text-xs" disabled={isLoading || total === 0} onClick={handleCsv}>
          {isLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <FileDown className="h-3 w-3" />} CSV
        </Button>
        {ledger.geo && (
          <Button variant="outline" size="sm" className="h-8 text-xs" disabled={isLoading || geo === 0} onClick={handleGeo}>
            <MapPin className="h-3 w-3" /> GeoJSON
          </Button>
        )}
      </div>
    </div>
  );
}