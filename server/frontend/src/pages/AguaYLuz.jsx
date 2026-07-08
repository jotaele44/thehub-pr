import React from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import ModulePageHeader from "@/components/shared/ModulePageHeader";
import EntityLedger from "@/components/shared/EntityLedger";
import AguaYLuzFeedTab from "@/components/feed/AguaYLuzFeedTab";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import { Droplets } from "lucide-react";
import { MODULES, REGIONS } from "@/lib/federation";
import { GENERIC_STATUS, SENSITIVITY, SEVERITY, CONFIDENCE } from "@/lib/chips";

const MODULE = MODULES.find((m) => m.name === "AguaYLuz-PR");
const ASSET_TYPES = ["Reservoir", "Dam", "PumpStation", "WaterPlant", "PowerPlant", "Substation", "Transmission", "Distribution", "Canal", "Other"];
const RISK_TYPES = ["Dependency", "Outage", "Maintenance", "Capacity", "DocumentationGap", "SourceGap", "Other"];

export default function AguaYLuz() {
  const assetFields = [
    { key: "asset_id", label: "Asset ID", required: true },
    { key: "name", label: "Name", required: true, full: true },
    { key: "asset_type", label: "Type", type: "select", options: ASSET_TYPES, required: true },
    { key: "municipality", label: "Municipality" },
    { key: "region", label: "Region", type: "select", options: REGIONS },
    { key: "operator", label: "Operator" },
    { key: "owner_agency", label: "Owner Agency" },
    { key: "latitude", label: "Latitude", type: "number" },
    { key: "longitude", label: "Longitude", type: "number" },
    { key: "status", label: "Status", type: "select", options: ["Active", "Inactive", "Unknown", "UnderReview"], required: true },
    { key: "sensitivity", label: "Sensitivity", type: "select", options: ["Public", "Internal", "Restricted"], required: true },
    { key: "summary", label: "Sanitized Summary", type: "textarea" },
  ];
  const assetColumns = [
    { key: "asset_id", label: "ID", render: (r) => <IdCode>{r.asset_id}</IdCode> },
    { key: "name", label: "Name", render: (r) => <span className="font-medium">{r.name}</span> },
    { key: "asset_type", label: "Type", render: (r) => <span className="text-muted-foreground">{r.asset_type}</span> },
    { key: "municipality", label: "Municipality" },
    { key: "status", label: "Status", render: (r) => <StatusChip map={GENERIC_STATUS} value={r.status} /> },
    { key: "sensitivity", label: "Sensitivity", render: (r) => <StatusChip map={SENSITIVITY} value={r.sensitivity} /> },
  ];

  const riskFields = [
    { key: "risk_id", label: "Risk ID", required: true },
    { key: "asset_id", label: "Asset ID", required: true },
    { key: "risk_type", label: "Risk Type", type: "select", options: RISK_TYPES, required: true },
    { key: "dependency_type", label: "Dependency", type: "select", options: ["WaterToPower", "PowerToWater", "Transport", "Communications", "Funding", "Unknown"] },
    { key: "related_asset_id", label: "Related Asset ID" },
    { key: "severity", label: "Severity", type: "select", options: ["Low", "Medium", "High", "Critical"], required: true },
    { key: "confidence", label: "Confidence", type: "select", options: ["Low", "Medium", "High"], required: true },
    { key: "status", label: "Status", type: "select", options: ["New", "Reviewing", "Mitigated", "Archived"], required: true },
    { key: "summary", label: "Summary", type: "textarea" },
  ];
  const riskColumns = [
    { key: "risk_id", label: "ID", render: (r) => <IdCode>{r.risk_id}</IdCode> },
    { key: "asset_id", label: "Asset", render: (r) => <IdCode>{r.asset_id}</IdCode> },
    { key: "risk_type", label: "Type", render: (r) => <span className="font-medium">{r.risk_type}</span> },
    { key: "severity", label: "Severity", render: (r) => <StatusChip map={SEVERITY} value={r.severity} /> },
    { key: "confidence", label: "Confidence", render: (r) => <StatusChip map={CONFIDENCE} value={r.confidence} /> },
    { key: "status", label: "Status", render: (r) => <StatusChip map={GENERIC_STATUS} value={r.status} /> },
  ];

  return (
    <div>
      <ModulePageHeader module={MODULE} icon={Droplets} />
      <div className="mb-4 rounded-lg border border-border bg-card px-4 py-2.5 text-xs text-muted-foreground">
        Infrastructure summaries are sanitized — no sensitive vulnerability detail is stored.
      </div>
      <Tabs defaultValue="feed">
        <TabsList className="mb-4">
          <TabsTrigger value="feed">Water + Power Feed</TabsTrigger>
          <TabsTrigger value="assets">Infrastructure Assets</TabsTrigger>
          <TabsTrigger value="risks">Continuity Risks</TabsTrigger>
        </TabsList>
        <TabsContent value="feed">
          <AguaYLuzFeedTab />
        </TabsContent>
        <TabsContent value="assets">
          <EntityLedger entityName="InfrastructureAssets" fields={assetFields} columns={assetColumns}
            searchKeys={["name", "asset_id", "municipality", "operator"]}
            filterDefs={[{ key: "asset_type", label: "Type", options: ASSET_TYPES }, { key: "status", label: "Status", options: ["Active", "Inactive", "Unknown", "UnderReview"] }]}
            addLabel="New Asset" emptyTitle="No assets" searchPlaceholder="Search assets…" />
        </TabsContent>
        <TabsContent value="risks">
          <EntityLedger entityName="ContinuityRisks" fields={riskFields} columns={riskColumns}
            searchKeys={["risk_id", "asset_id", "summary"]}
            filterDefs={[{ key: "risk_type", label: "Type", options: RISK_TYPES }, { key: "severity", label: "Severity", options: ["Low", "Medium", "High", "Critical"] }]}
            addLabel="New Risk" emptyTitle="No risks"
            emptyDescription="Continuity risk assessments require asset-level enrichment not yet in the canonical federation export — data pending richer AguaYLuz-PR intake."
            searchPlaceholder="Search risks…" />
        </TabsContent>
      </Tabs>
    </div>
  );
}