import React from "react";
import { cn } from "@/lib/utils";
import { LayoutGrid, AlarmClock, Table2, Columns3 } from "lucide-react";

const VIEWS = [
  { key: "grouped", label: "Grouped by Program", icon: LayoutGrid },
  { key: "urgency", label: "Urgency Queue", icon: AlarmClock },
  { key: "flat", label: "Flat Table", icon: Table2 },
  { key: "board", label: "Lifecycle Board", icon: Columns3 },
];

export default function ViewToggle({ value, onChange }) {
  return (
    <div className="inline-flex items-center gap-1 rounded-lg border border-border bg-card p-1">
      {VIEWS.map((v) => {
        const Icon = v.icon;
        const active = value === v.key;
        return (
          <button
            key={v.key}
            onClick={() => onChange(v.key)}
            className={cn(
              "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors",
              active ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Icon className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">{v.label}</span>
          </button>
        );
      })}
    </div>
  );
}