import React from "react";
import { cn } from "@/lib/utils";
import { GAP_CHIP, chipClass } from "@/lib/chips";
import { AlertTriangle } from "lucide-react";

export default function GapChips({ gaps = [], className }) {
  if (!gaps.length) return null;
  return (
    <div className={cn("flex flex-wrap gap-1", className)}>
      {gaps.map((g) => (
        <span
          key={g}
          className={cn(
            "inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium border",
            chipClass(GAP_CHIP, g)
          )}
        >
          <AlertTriangle className="h-2.5 w-2.5" />
          {g}
        </span>
      ))}
    </div>
  );
}