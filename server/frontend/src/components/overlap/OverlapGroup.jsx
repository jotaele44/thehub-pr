import React from "react";
import { MapPin, Map } from "lucide-react";
import OverlapCaseCard from "./OverlapCaseCard";

export default function OverlapGroup({ group, moduleA, moduleB }) {
  const Icon = group.kind === "Municipality" ? MapPin : Map;
  return (
    <div className="rounded-lg border border-border bg-secondary/40 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border bg-card/40">
        <Icon className="h-4 w-4 text-status-warning-fg" />
        <span className="text-sm font-medium text-foreground">{group.label}</span>
        <span className="text-xs text-muted-foreground">{group.kind} overlap</span>
        <span className="ml-auto text-xs text-muted-foreground">
          {group.a.length} ↔ {group.b.length}
        </span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-border">
        <div className="p-3 space-y-2">
          <div className="text-xs font-medium text-muted-foreground mb-1">{moduleA}</div>
          {group.a.map((c) => <OverlapCaseCard key={c.id} caseRow={c} />)}
        </div>
        <div className="p-3 space-y-2">
          <div className="text-xs font-medium text-muted-foreground mb-1">{moduleB}</div>
          {group.b.map((c) => <OverlapCaseCard key={c.id} caseRow={c} />)}
        </div>
      </div>
    </div>
  );
}