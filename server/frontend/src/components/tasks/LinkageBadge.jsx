import React from "react";
import { cn } from "@/lib/utils";
import { Link2, Link2Off } from "lucide-react";

export default function LinkageBadge({ label, className }) {
  if (!label) return null;
  const unlinked = label === "Unlinked";
  const Icon = unlinked ? Link2Off : Link2;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium border",
        unlinked
          ? "bg-slate-500/15 text-slate-400 border-slate-500/30"
          : "bg-indigo-500/10 text-indigo-300 border-indigo-500/25",
        className
      )}
    >
      <Icon className="h-2.5 w-2.5" />
      {label}
    </span>
  );
}