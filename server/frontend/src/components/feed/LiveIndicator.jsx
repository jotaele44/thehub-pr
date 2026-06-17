import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";

function ago(ts) {
  if (!ts) return "never";
  const s = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  return `${Math.floor(m / 60)}h ago`;
}

// Live status badge: shows Live / Stale / Degraded honestly so the UI never
// claims "live" after a failure or a long gap. Self-ticks every second so the
// stale transition happens even when no query is firing.
export default function LiveIndicator({ dataUpdatedAt, isFetching, isError, intervalMs, staleAfterMs = 90000 }) {
  const [, tick] = useState(0);
  const qc = useQueryClient();

  useEffect(() => {
    const t = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, []);

  const refreshNow = () => {
    qc.invalidateQueries({ queryKey: ["entity", "LiveFeedItems"] });
    qc.invalidateQueries({ queryKey: ["entity", "LiveFeedSources"] });
    qc.invalidateQueries({ queryKey: ["entity", "LiveFeedRuns"] });
  };

  const stale = !!dataUpdatedAt && Date.now() - dataUpdatedAt > staleAfterMs;
  const degraded = isError || stale;

  const dot = degraded ? "bg-amber-400" : "bg-emerald-400";
  const text = degraded ? "text-amber-300" : "text-emerald-300";
  const label = isError ? "Degraded" : stale ? "Stale" : "Live";

  return (
    <div className="flex items-center gap-3 text-xs text-muted-foreground">
      <span className="inline-flex items-center gap-1.5">
        <span className="relative flex h-2 w-2">
          {!degraded && (
            <span className={`absolute inline-flex h-full w-full rounded-full ${dot} opacity-75 ${isFetching ? "animate-ping" : "animate-pulse"}`} />
          )}
          <span className={`relative inline-flex h-2 w-2 rounded-full ${dot}`} />
        </span>
        <span className={`${text} font-medium`}>{label}</span>
      </span>
      <span>updated {ago(dataUpdatedAt)}</span>
      {intervalMs && !degraded && <span className="hidden sm:inline">· auto every {Math.round(intervalMs / 1000)}s</span>}
      {isError && <span className="hidden sm:inline text-amber-400/80">· fetch error, retrying</span>}
      <Button size="sm" variant="ghost" className="h-7 px-2" onClick={refreshNow}>
        <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
      </Button>
    </div>
  );
}