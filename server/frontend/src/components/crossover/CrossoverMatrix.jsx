import React from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import StatusChip from "@/components/shared/StatusChip";
import { MODULE_SHORT, TYPE_CHIP } from "@/lib/crossover-config";
import { TIER } from "@/lib/chips";
import { cn } from "@/lib/utils";

export default function CrossoverMatrix({ matrix, onSelectPair }) {
  return (
    <div className="rounded-xl border border-border bg-card overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Module Pair</TableHead>
            <TableHead className="text-right">Total</TableHead>
            <TableHead className="text-right">Verified</TableHead>
            <TableHead className="text-right">Pending</TableHead>
            <TableHead className="text-right">Contradicted</TableHead>
            <TableHead className="text-right">Top Score</TableHead>
            <TableHead>Dominant Tier</TableHead>
            <TableHead>Common Type</TableHead>
            <TableHead className="text-right">Open Gaps</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {matrix.map((m) => (
            <TableRow
              key={m.key}
              className={cn("cursor-pointer", m.count === 0 && "opacity-50")}
              onClick={() => m.count > 0 && onSelectPair?.(m.key)}
            >
              <TableCell className="font-medium whitespace-nowrap">
                {MODULE_SHORT[m.a]} ↔ {MODULE_SHORT[m.b]}
              </TableCell>
              <TableCell className="text-right font-mono-id">{m.count}</TableCell>
              <TableCell className="text-right font-mono-id text-emerald-300">{m.verified}</TableCell>
              <TableCell className="text-right font-mono-id text-blue-300">{m.pending}</TableCell>
              <TableCell className="text-right font-mono-id text-amber-300">{m.contradicted}</TableCell>
              <TableCell className="text-right font-mono-id">{m.topScore || "—"}</TableCell>
              <TableCell>{m.dominantTier !== "—" ? <StatusChip map={TIER} value={m.dominantTier} /> : "—"}</TableCell>
              <TableCell>{m.commonType !== "—" ? <StatusChip map={TYPE_CHIP} value={m.commonType} /> : "—"}</TableCell>
              <TableCell className="text-right font-mono-id text-yellow-300">{m.gaps || "—"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}