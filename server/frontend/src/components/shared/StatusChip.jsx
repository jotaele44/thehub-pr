import React from "react";
import { cn } from "@/lib/utils";
import { chipClass } from "@/lib/chips";

/** @param {{map: Record<string, string>, value: unknown, className?: string}} props */
export default function StatusChip({ map, value, className }) {
  if (value === undefined || value === null || value === "") return <span className="text-muted-foreground text-xs">—</span>;
  return (
    <span className={cn(
      "inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border whitespace-nowrap",
      chipClass(map, value),
      className
    )}>
      {String(value)}
    </span>
  );
}