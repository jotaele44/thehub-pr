import React from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import EmptyState from "@/components/shared/EmptyState";
import { EXPORTS_STATUS } from "@/lib/export-config";
import { History } from "lucide-react";

const fmt = (d) => (d ? new Date(d).toLocaleString() : "—");

// Recorded export ledger — provenance trail of who exported what, when.
export default function ExportHistory({ records }) {
  if (!records.length) {
    return (
      <EmptyState
        icon={History}
        title="No exports recorded yet"
        description="Each CSV or GeoJSON export is logged here with record count, format, sensitivity, and the analyst who generated it."
      />
    );
  }

  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Export ID</TableHead>
            <TableHead>Ledger</TableHead>
            <TableHead>Format</TableHead>
            <TableHead>Records</TableHead>
            <TableHead>Sensitivity</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Generated</TableHead>
            <TableHead>By</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {records.map((r) => (
            <TableRow key={r.id || r.export_id}>
              <TableCell><IdCode>{r.export_id}</IdCode></TableCell>
              <TableCell className="text-xs">{r.ledger} <span className="text-muted-foreground">· {r.module}</span></TableCell>
              <TableCell className="text-xs">{r.export_format}</TableCell>
              <TableCell className="text-xs">{r.record_count}</TableCell>
              <TableCell><StatusChip map={{ Public: "bg-slate-500/15 text-slate-300 border-slate-500/30", Internal: "bg-amber-500/15 text-amber-300 border-amber-500/30", Restricted: "bg-red-500/15 text-red-300 border-red-500/30" }} value={r.sensitivity_max} /></TableCell>
              <TableCell><StatusChip map={EXPORTS_STATUS} value={r.status} /></TableCell>
              <TableCell className="text-xs text-muted-foreground">{fmt(r.generated_at)}</TableCell>
              <TableCell className="text-xs text-muted-foreground">{r.generated_by || "—"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}