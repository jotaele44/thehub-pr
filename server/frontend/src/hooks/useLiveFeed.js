import { useMemo } from "react";
import { useEntityData } from "@/hooks/useEntityData";
import { LIVE_INTERVAL_MS, STALE_AFTER_MS } from "@/lib/feed-config";

// Shared live-feed data layer for MoneySweep-PR and AguaYLuz-PR.
// Scopes feed items, sources, and runs to one module.
// Auto-refreshes every 30s so dashboards stay live without manual reload.
export function useLiveFeed(module, { live = true } = {}) {
  const poll = live ? LIVE_INTERVAL_MS : undefined;
  const { rows: allItems, isLoading: li, isFetching: fi, isError: ei, dataUpdatedAt, create: createItem, update: updateItem, saving } = useEntityData("LiveFeedItems", "-created_date", { refetchInterval: poll });
  const { rows: allSources, isLoading: ls, isError: es, update: updateSource } = useEntityData("LiveFeedSources", "-created_date", { refetchInterval: poll });
  const { rows: allRuns, isLoading: lr, isError: er } = useEntityData("LiveFeedRuns", "-created_date", { refetchInterval: poll });

  const items = useMemo(() => allItems.filter((i) => i.module === module), [allItems, module]);
  const sources = useMemo(() => allSources.filter((s) => s.module === module), [allSources, module]);
  const runs = useMemo(
    () => allRuns.filter((r) => r.module === module)
      .sort((a, b) => new Date(b.started_at || 0) - new Date(a.started_at || 0)),
    [allRuns, module]
  );

  const feed = useMemo(
    () => [...items].sort((a, b) =>
      new Date(b.last_refetched_at || b.created_date || 0) - new Date(a.last_refetched_at || a.created_date || 0)
    ),
    [items]
  );

  const staging = useMemo(
    () => feed.filter((i) => ["New", "Updated", "NeedsReview", "Verified"].includes(i.sync_status)),
    [feed]
  );

  const lastRefresh = runs[0]?.finished_at || runs[0]?.started_at || null;

  // Per-source freshness so one stale source isn't hidden by the aggregate timestamp.
  const sourceFreshness = useMemo(() => sources.map((s) => {
    const ts = s.last_refetched_at ? new Date(s.last_refetched_at).getTime() : null;
    const stale = !ts || (Date.now() - ts) > STALE_AFTER_MS;
    return { source_id: s.source_id, label: s.label, last: ts, stale, health_status: s.health_status };
  }), [sources]);

  const isError = ei || es || er;
  const isStale = !!dataUpdatedAt && (Date.now() - dataUpdatedAt) > STALE_AFTER_MS;

  return {
    isLoading: li || ls || lr,
    isFetching: fi,
    isError,
    isStale,
    dataUpdatedAt,
    intervalMs: LIVE_INTERVAL_MS,
    staleAfterMs: STALE_AFTER_MS,
    sourceFreshness,
    items: feed, sources, runs, staging, lastRefresh,
    createItem, updateItem, updateSource, saving,
  };
}