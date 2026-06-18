import React from "react";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";

// defs: [{ key, label, options:[{value,label}] }]
export default function TaskFilterBar({ filters, setFilter, defs, onClear, hasActive }) {
  return (
    <div className="flex flex-col gap-3 mb-4">
      <div className="relative flex-1 min-w-[200px]">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          value={filters.search || ""}
          onChange={(e) => setFilter("search", e.target.value)}
          placeholder="Search tasks, IDs, assignees…"
          className="pl-9 bg-card border-border"
        />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {defs.map((f) => (
          <Select key={f.key} value={filters[f.key] || "all"} onValueChange={(v) => setFilter(f.key, v)}>
            <SelectTrigger className="w-auto min-w-[120px] bg-card border-border h-9 text-sm">
              <SelectValue placeholder={f.label} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All {f.label}</SelectItem>
              {f.options.map((o) => (
                <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        ))}
        {hasActive && (
          <Button variant="ghost" size="sm" onClick={onClear} className="text-xs text-muted-foreground">
            <X className="h-3.5 w-3.5 mr-1" /> Clear
          </Button>
        )}
      </div>
    </div>
  );
}