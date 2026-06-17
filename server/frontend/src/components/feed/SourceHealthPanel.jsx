import React from "react";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ExternalLink } from "lucide-react";

const HEALTH = {
  Healthy: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  Degraded: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  Failed: "bg-red-500/15 text-red-300 border-red-500/30",
  NeedsReview: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  Unknown: "bg-muted text-muted-foreground border-border",
};

const FRESH = {
  Fresh: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  Stale: "bg-amber-500/15 text-amber-300 border-amber-500/30",
};

export default function SourceHealthPanel({ sources, freshness = [] }) {
  if (!sources.length) {
    return <p className="text-sm text-muted-foreground p-6 text-center">No feed sources configured for this module.</p>;
  }
  const freshById = Object.fromEntries(freshness.map((f) => [f.source_id, f]));
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Source</TableHead>
          <TableHead>System</TableHead>
          <TableHead>Fetch</TableHead>
          <TableHead>Health</TableHead>
          <TableHead>Freshness</TableHead>
          <TableHead>Last Run</TableHead>
          <TableHead>Items</TableHead>
          <TableHead>Link</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sources.map((s) => (
          <TableRow key={s.id}>
            <TableCell><span className="font-medium">{s.label}</span><div><IdCode>{s.source_id}</IdCode></div></TableCell>
            <TableCell className="text-muted-foreground">{s.source_system}</TableCell>
            <TableCell className="text-muted-foreground">{s.fetch_kind}</TableCell>
            <TableCell><StatusChip map={HEALTH} value={s.health_status} /></TableCell>
            <TableCell><StatusChip map={FRESH} value={freshById[s.source_id]?.stale ? "Stale" : "Fresh"} /></TableCell>
            <TableCell className="text-muted-foreground text-xs">{s.last_run_status}{s.last_refetched_at ? ` · ${new Date(s.last_refetched_at).toLocaleString()}` : ""}</TableCell>
            <TableCell className="font-mono-id text-xs">{s.last_item_count ?? 0}</TableCell>
            <TableCell>
              {s.source_url && <a href={s.source_url} target="_blank" rel="noreferrer" className="text-sky-300"><ExternalLink className="h-3.5 w-3.5" /></a>}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}