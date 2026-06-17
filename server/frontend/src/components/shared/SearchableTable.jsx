import React, { useState, useMemo } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import { cn } from "@/lib/utils";
import EmptyState from "./EmptyState";

// columns: [{ key, label, render?(row), sortable?, className? }]
export default function SearchableTable({ columns, rows, onRowClick, emptyTitle, emptyDescription, initialSort }) {
  const [sortKey, setSortKey] = useState(initialSort?.key || null);
  const [sortDir, setSortDir] = useState(initialSort?.dir || "asc");

  const sorted = useMemo(() => {
    if (!sortKey) return rows;
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = a[sortKey] ?? "";
      const bv = b[sortKey] ?? "";
      if (av < bv) return sortDir === "asc" ? -1 : 1;
      if (av > bv) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return copy;
  }, [rows, sortKey, sortDir]);

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("asc"); }
  };

  if (!rows.length) {
    return (
      <div className="rounded-xl border border-border bg-card">
        <EmptyState title={emptyTitle} description={emptyDescription} />
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="border-border hover:bg-transparent">
              {columns.map((col) => (
                <TableHead key={col.key} className={cn("text-xs uppercase tracking-wide text-muted-foreground", col.className)}>
                  {col.sortable === false ? col.label : (
                    <button onClick={() => toggleSort(col.key)} className="inline-flex items-center gap-1 hover:text-foreground transition-colors">
                      {col.label}
                      {sortKey === col.key ? (sortDir === "asc" ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />) : <ArrowUpDown className="h-3 w-3 opacity-40" />}
                    </button>
                  )}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((row) => (
              <TableRow
                key={row.id}
                onClick={() => onRowClick?.(row)}
                className={cn("border-border", onRowClick && "cursor-pointer hover:bg-secondary/50")}
              >
                {columns.map((col) => (
                  <TableCell key={col.key} className={cn("text-sm", col.className)}>
                    {col.render ? col.render(row) : (row[col.key] ?? <span className="text-muted-foreground">—</span>)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}