import React from "react";
import { GitBranch, ArrowRight } from "lucide-react";

export default function LineageBanner({ program }) {
  const sourceRepo = program?.source_repo || "thehub-pr";
  const appName = program?.name || "INTSYS-PR";
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-3">
        <GitBranch className="h-3.5 w-3.5" /> Source Repo Lineage
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex flex-col">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Source / Legacy Repo</span>
          <span className="font-mono-id text-lg text-amber-300">{sourceRepo}</span>
        </div>
        <ArrowRight className="h-5 w-5 text-muted-foreground" />
        <div className="flex flex-col">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Federation Successor App</span>
          <span className="font-mono-id text-lg text-foreground">{appName}</span>
        </div>
      </div>
      <p className="text-xs text-muted-foreground mt-4 max-w-3xl">
        {program?.description || "Federation operational transition layer for thehub-pr."}
      </p>
      <div className="flex flex-wrap gap-x-6 gap-y-2 mt-4 text-xs">
        <span className="text-muted-foreground">Transition status: <span className="text-foreground font-mono-id">{program?.transition_status || "—"}</span></span>
        <span className="text-muted-foreground">Lead vector: <span className="text-foreground font-mono-id">{program?.lead_vector || "—"}</span></span>
        <span className="text-muted-foreground">Parity: <span className="text-foreground font-mono-id">{program?.parity_status || "—"}</span></span>
      </div>
    </div>
  );
}