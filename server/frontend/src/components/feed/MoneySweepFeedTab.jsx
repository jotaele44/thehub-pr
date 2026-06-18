import React, { useState } from "react";
import { federation } from "@/api/federationClient";
import { useLiveFeed } from "@/hooks/useLiveFeed";
import { useQueryClient } from "@tanstack/react-query";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import FeedKpiCards from "@/components/feed/FeedKpiCards";
import LiveIndicator from "@/components/feed/LiveIndicator";
import StagingQueue from "@/components/feed/StagingQueue";
import SourceHealthPanel from "@/components/feed/SourceHealthPanel";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { RefreshCw, FileStack, DollarSign, UserPlus, AlertTriangle, ExternalLink } from "lucide-react";
import { promoteFeedItem } from "@/lib/promote-feed";
import { toast } from "sonner";

const fmtMoney = (n) => (n || n === 0) ? `$${Number(n).toLocaleString()}` : "—";
const SYNC = {
  New: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  Verified: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  Promoted: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  NeedsReview: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  Deferred: "bg-muted text-muted-foreground border-border",
};

export default function MoneySweepFeedTab() {
  const { isLoading, items, sources, staging, lastRefresh, isFetching, isError, dataUpdatedAt, intervalMs, staleAfterMs, sourceFreshness, updateItem, saving } = useLiveFeed("MoneySweep-PR");
  const [refetching, setRefetching] = useState(false);
  const qc = useQueryClient();

  const newCount = items.filter((i) => i.sync_status === "New").length;
  const totalValue = items.reduce((s, i) => s + (Number(i.amount) || 0), 0);
  const vendors = new Set(items.map((i) => i.vendor_name).filter(Boolean)).size;
  const needsReview = items.filter((i) => i.sync_status === "NeedsReview").length;

  const refetch = async () => {
    setRefetching(true);
    try {
      const res = await federation.functions.invoke("refetchUSASpending", { source_id: "usaspending-pr", limit: 25 });
      const d = res.data || {};
      if (d.error) toast.error(`Refetch failed: ${d.error}`);
      else toast.success(`Fetched ${d.items_fetched} · ${d.items_new} new`);
      qc.invalidateQueries({ queryKey: ["entity", "LiveFeedItems"] });
      qc.invalidateQueries({ queryKey: ["entity", "LiveFeedSources"] });
      qc.invalidateQueries({ queryKey: ["entity", "LiveFeedRuns"] });
    } catch (e) {
      toast.error(`Refetch error: ${e.message}`);
    }
    setRefetching(false);
  };

  const setStatus = async (item, sync_status) => {
    try {
      if (sync_status === "Promoted") {
        const recordId = await promoteFeedItem(item);
        await updateItem({ id: item.id, data: { sync_status, promoted_record_id: recordId } });
        toast.success(`Promoted to Contract ${recordId}`);
        qc.invalidateQueries({ queryKey: ["entity", "Contracts"] });
        qc.invalidateQueries({ queryKey: ["entity", "Vendors"] });
      } else if (sync_status === "Verified") {
        let reviewer = null;
        try { reviewer = (await federation.auth.me())?.email || null; } catch { reviewer = null; }
        await updateItem({ id: item.id, data: { sync_status, verified_by: reviewer, verified_at: new Date().toISOString() } });
        toast.success("Verified — ready to promote");
      } else {
        await updateItem({ id: item.id, data: { sync_status } });
      }
    } catch (e) {
      toast.error(`Promotion failed: ${e.message}`);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div className="flex items-center gap-4 flex-wrap">
          <LiveIndicator dataUpdatedAt={dataUpdatedAt} isFetching={isFetching} isError={isError} intervalMs={intervalMs} staleAfterMs={staleAfterMs} />
          <span className="text-xs text-muted-foreground">
            {lastRefresh ? `Last fetch run: ${new Date(lastRefresh).toLocaleString()}` : "No refresh runs yet"}
          </span>
        </div>
        <Button size="sm" onClick={refetch} disabled={refetching}>
          <RefreshCw className={`h-4 w-4 mr-2 ${refetching ? "animate-spin" : ""}`} /> Refetch USAspending
        </Button>
      </div>

      <FeedKpiCards cards={[
        { label: "New Awards", value: newCount, icon: FileStack },
        { label: "Total Value", value: fmtMoney(totalValue), icon: DollarSign, accent: "text-emerald-300" },
        { label: "Vendors", value: vendors, icon: UserPlus },
        { label: "Needs Review", value: needsReview, icon: AlertTriangle, alert: needsReview > 0 },
      ]} />

      <Tabs defaultValue="feed">
        <TabsList className="mb-4">
          <TabsTrigger value="feed">Live Feed</TabsTrigger>
          <TabsTrigger value="staging">Staging Queue ({staging.length})</TabsTrigger>
          <TabsTrigger value="sources">Sources</TabsTrigger>
        </TabsList>

        <TabsContent value="feed">
          {isLoading ? (
            <p className="text-sm text-muted-foreground p-6 text-center">Loading feed…</p>
          ) : !items.length ? (
            <p className="text-sm text-muted-foreground p-6 text-center">No fetched records yet. Click “Refetch USAspending”.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Vendor</TableHead>
                  <TableHead>Agency</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Stream</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Award</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((i) => (
                  <TableRow key={i.id}>
                    <TableCell><span className="font-medium">{i.vendor_name || "—"}</span></TableCell>
                    <TableCell className="text-muted-foreground">{i.agency_name || "—"}</TableCell>
                    <TableCell className="font-mono-id text-xs">{fmtMoney(i.amount)}</TableCell>
                    <TableCell className="text-muted-foreground text-xs">{i.funding_stream}</TableCell>
                    <TableCell><StatusChip map={SYNC} value={i.sync_status} /></TableCell>
                    <TableCell>
                      {i.source_url
                        ? <a href={i.source_url} target="_blank" rel="noreferrer" className="text-sky-300 flex items-center gap-1"><IdCode>{i.award_id}</IdCode><ExternalLink className="h-3 w-3" /></a>
                        : <IdCode>{i.award_id}</IdCode>}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </TabsContent>

        <TabsContent value="staging">
          <StagingQueue
            items={staging}
            saving={saving}
            onSetStatus={setStatus}
            renderMeta={(it) => `${it.agency_name || "—"} · ${fmtMoney(it.amount)}`}
          />
        </TabsContent>

        <TabsContent value="sources">
          <SourceHealthPanel sources={sources} freshness={sourceFreshness} />
        </TabsContent>
      </Tabs>
    </div>
  );
}