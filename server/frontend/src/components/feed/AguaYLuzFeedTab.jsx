import React, { useState } from "react";
import { federation } from "@/api/federationClient";
import { useLiveFeed } from "@/hooks/useLiveFeed";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import RecordSheet from "@/components/shared/RecordSheet";
import FeedKpiCards from "@/components/feed/FeedKpiCards";
import LiveIndicator from "@/components/feed/LiveIndicator";
import StagingQueue from "@/components/feed/StagingQueue";
import SourceHealthPanel from "@/components/feed/SourceHealthPanel";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Plus, Zap, Droplet, MapPin, AlertTriangle } from "lucide-react";
import { promoteFeedItem } from "@/lib/promote-feed";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "@/components/ui/use-toast";

const STATUS = {
  New: "bg-status-info/15 text-status-info-fg border-status-info/30",
  Verified: "bg-status-success/15 text-status-success-fg border-status-success/30",
  Promoted: "bg-status-success/15 text-status-success-fg border-status-success/30",
  NeedsReview: "bg-status-warning/15 text-status-warning-fg border-status-warning/30",
  Deferred: "bg-muted text-muted-foreground border-border",
};
const DOMAINS = ["Water", "Power", "Wastewater", "Hydrology"];
const SOURCE_SYSTEMS = ["LUMA", "PRASA", "EPA SDWIS", "EPA ECHO", "USGS", "manual"];

const EVENT_FIELDS = [
  { key: "feed_item_id", label: "Feed Item ID", required: true, placeholder: "ayl-001" },
  { key: "source_id", label: "Source ID", required: true, placeholder: "luma-outages" },
  { key: "source_system", label: "Source System", type: "select", options: SOURCE_SYSTEMS, required: true },
  { key: "utility_domain", label: "Utility Domain", type: "select", options: DOMAINS, required: true },
  { key: "event_type", label: "Event Type", placeholder: "Outage, advisory, violation…" },
  { key: "title", label: "Title", required: true, full: true },
  { key: "facility_name", label: "Facility Name" },
  { key: "facility_type", label: "Facility Type" },
  { key: "municipality", label: "Municipality" },
  { key: "customers_affected", label: "Customers Affected", type: "number" },
  { key: "latitude", label: "Latitude", type: "number" },
  { key: "longitude", label: "Longitude", type: "number" },
  { key: "source_url", label: "Source URL", full: true },
  { key: "evidence_tier", label: "Evidence Tier", type: "select", options: ["T1", "T2", "T3", "T4"] },
  { key: "summary", label: "Summary", type: "textarea" },
];

export default function AguaYLuzFeedTab() {
  const { isLoading, items, sources, staging, isFetching, isError, dataUpdatedAt, intervalMs, staleAfterMs, sourceFreshness, createItem, updateItem, saving } = useLiveFeed("AguaYLuz-PR");
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();

  const powerActive = items.filter((i) => i.utility_domain === "Power" && i.sync_status !== "Deferred").length;
  const waterActive = items.filter((i) => i.utility_domain === "Water" && i.sync_status !== "Deferred").length;
  const munis = new Set(items.map((i) => i.municipality).filter(Boolean)).size;
  const needsReview = items.filter((i) => i.sync_status === "NeedsReview").length;

  const setStatus = async (item, sync_status) => {
    try {
      if (sync_status === "Promoted") {
        const recordId = await promoteFeedItem(item);
        await updateItem({ id: item.id, data: { sync_status, promoted_record_id: recordId } });
        toast({ title: `Promoted to Asset ${recordId}` });
        qc.invalidateQueries({ queryKey: ["entity", "InfrastructureAssets"] });
      } else if (sync_status === "Verified") {
        let reviewer = null;
        try { reviewer = (await federation.auth.me())?.email || null; } catch { reviewer = null; }
        await updateItem({ id: item.id, data: { sync_status, verified_by: reviewer, verified_at: new Date().toISOString() } });
        toast({ title: "Verified — ready to promote" });
      } else {
        await updateItem({ id: item.id, data: { sync_status } });
      }
    } catch (e) {
      toast({ title: `Promotion failed: ${e.message}`, variant: "destructive" });
    }
  };
  const handleSave = async (data) => {
    await createItem({ ...data, module: "AguaYLuz-PR", sync_status: "New", last_refetched_at: new Date().toISOString() });
    setOpen(false);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div className="flex items-center gap-4 flex-wrap">
          <LiveIndicator dataUpdatedAt={dataUpdatedAt} isFetching={isFetching} isError={isError} intervalMs={intervalMs} staleAfterMs={staleAfterMs} />
          <span className="text-xs text-muted-foreground">
            LUMA / PRASA lack open APIs — log service events manually; EPA/USGS can be wired later.
          </span>
        </div>
        <Button size="sm" onClick={() => setOpen(true)}><Plus className="h-4 w-4 mr-2" /> Add Service Event</Button>
      </div>

      <FeedKpiCards cards={[
        { label: "Power Events", value: powerActive, icon: Zap, accent: "text-status-warning-fg" },
        { label: "Water Events", value: waterActive, icon: Droplet, accent: "text-status-info-fg" },
        { label: "Municipalities", value: munis, icon: MapPin },
        { label: "Needs Review", value: needsReview, icon: AlertTriangle, alert: needsReview > 0 },
      ]} />

      <Tabs defaultValue="feed">
        <TabsList className="mb-4">
          <TabsTrigger value="feed">Service Feed</TabsTrigger>
          <TabsTrigger value="staging">Staging Queue ({staging.length})</TabsTrigger>
          <TabsTrigger value="sources">Sources</TabsTrigger>
        </TabsList>

        <TabsContent value="feed">
          {isLoading ? (
            <p className="text-sm text-muted-foreground p-6 text-center">Loading feed…</p>
          ) : !items.length ? (
            <p className="text-sm text-muted-foreground p-6 text-center">No service events yet. Click “Add Service Event”.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Domain</TableHead>
                  <TableHead>Event</TableHead>
                  <TableHead>Facility</TableHead>
                  <TableHead>Municipality</TableHead>
                  <TableHead>Affected</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((i) => (
                  <TableRow key={i.id}>
                    <TableCell className="text-muted-foreground">{i.utility_domain || "—"}</TableCell>
                    <TableCell><span className="font-medium">{i.title}</span><div><IdCode>{i.event_type}</IdCode></div></TableCell>
                    <TableCell className="text-muted-foreground">{i.facility_name || "—"}</TableCell>
                    <TableCell>{i.municipality || "—"}</TableCell>
                    <TableCell className="font-mono-id text-xs">{i.customers_affected ?? "—"}</TableCell>
                    <TableCell><StatusChip map={STATUS} value={i.sync_status} /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </TabsContent>

        <TabsContent value="staging">
          <StagingQueue items={staging} saving={saving} onSetStatus={setStatus}
            renderMeta={(it) => `${it.utility_domain || "—"} · ${it.municipality || "—"}${it.customers_affected ? ` · ${it.customers_affected} affected` : ""}`} />
        </TabsContent>

        <TabsContent value="sources">
          <SourceHealthPanel sources={sources} freshness={sourceFreshness} />
        </TabsContent>
      </Tabs>

      <RecordSheet open={open} onOpenChange={setOpen} title="Add Service Event" fields={EVENT_FIELDS} onSave={handleSave} saving={saving} />
    </div>
  );
}