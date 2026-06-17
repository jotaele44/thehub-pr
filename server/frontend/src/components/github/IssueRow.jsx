import React from "react";
import { Button } from "@/components/ui/button";
import { ExternalLink, CircleDot, CheckCircle2, GitPullRequest, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export default function IssueRow({ item, isPull, onToggle, busy }) {
  const open = item.state === "open";
  const Icon = isPull ? GitPullRequest : (open ? CircleDot : CheckCircle2);
  return (
    <div className="flex items-start gap-3 px-4 py-3 border-b border-border last:border-0 hover:bg-secondary/40">
      <Icon className={cn("h-4 w-4 mt-0.5 shrink-0", open ? "text-green-400" : "text-violet-400")} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm truncate">{item.title}</span>
          <span className="font-mono-id text-xs text-muted-foreground shrink-0">#{item.number}</span>
          {isPull && item.draft && <span className="text-[10px] uppercase tracking-wide text-muted-foreground border border-border rounded px-1">draft</span>}
        </div>
        <div className="flex flex-wrap items-center gap-1.5 mt-1">
          <span className="text-xs text-muted-foreground">{open ? "Open" : "Closed"} · {item.user || "—"}</span>
          {item.labels?.map((l) => (
            <span key={l} className="text-[10px] rounded bg-secondary border border-border px-1.5 py-0.5 text-muted-foreground">{l}</span>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-1 shrink-0">
        {!isPull && (
          <Button variant="outline" size="sm" className="h-7 text-xs" disabled={busy} onClick={() => onToggle(item)}>
            {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : (open ? "Close" : "Reopen")}
          </Button>
        )}
        <Button variant="ghost" size="icon" className="h-7 w-7" asChild>
          <a href={item.html_url} target="_blank" rel="noopener noreferrer"><ExternalLink className="h-3.5 w-3.5" /></a>
        </Button>
      </div>
    </div>
  );
}