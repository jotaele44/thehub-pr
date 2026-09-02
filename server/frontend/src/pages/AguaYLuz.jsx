import React from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import ModulePageHeader from "@/components/shared/ModulePageHeader";
import EntityLedger from "@/components/shared/EntityLedger";
import AguaYLuzFeedTab from "@/components/feed/AguaYLuzFeedTab";
import IntelligenceWorkspace from "@/components/intelligence/IntelligenceWorkspace";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import { Droplets } from "lucide-react";
import { MODULES, REGIONS } from "@/lib/federation";
import { INTELLIGENCE_ADAPTERS } from "@/lib/intelligenceAdapters";
import { GENERIC_STATUS, SENSITIVITY, SEVERITY, CONFIDENCE, REVIEW_STATUS } from "@/lib/chips";

const MODULE = MODULES.find((m) => m.name === "AguaYLuz-PR");
const ASSET_TYPES = ["Reservoir", "Dam", "PumpStation", "WaterPlant", "PowerPlant", "Substation", "Transmission", "Distribution", "Canal", "Other"];
const RISK_TYPES = ["Dependency", "Outage", "Maintenance", "Capacity", "DocumentationGap", "SourceGap", "Other"];

// AguaYLuz's alert-system modules (its config/alert_modules.yaml). Continuity Risks
// covers only the water/power continuity subset, and the Water + Power Feed only the
// four modules that map to a utility domain — so hazard modules (seismic, weather)
// reached the hub in the `alerts` stream but had nowhere to be read. This tab is
// where the whole layer lands.
const ALERT_MODULES = [
  "CONTAMINATION", "HYDRO_OPS", "POWER_OPS", "WEATHER_HAZARD", "SEISMIC_GEO",
  "DAM_SAFETY", "PUBLIC_NOTICE", "TRANSPORT_ACCESS", "TELECOM_SCADA", "INDUSTRIAL",
];
const ALERT_REVIEW_STATES = ["Open", "Acknowledged", "Closed", "Rejected"];

// Producer alerts carry the workbook's 0–5 operational severity; the hub's chips speak
// Low/Medium/High/Critical. Same banding as `_SEVERITY_BAND` in src/hub/ingest.py.
const SEVERITY_BAND = { 0: "Low", 1: "Low", 2: "Medium", 3: "High", 4: "Critical", 5: "Critical" };
const severityBand = (s) => (typeof s === "number" ? SEVERITY_BAND[s] : undefined);

// GovernanceAlerts is federation-wide; scope the tab to rows aguayluz-pr contributed.
const isAguayluzAlert = (row) => (row?._producers || []).includes("aguayluz-pr");

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

  const alertColumns = [
    { key: "module", label: "Module", render: (r) => <span className="font-medium">{r.module || "—"}</span> },
    {
      key: "severity",
      label: "Severity",
      render: (r) => <StatusChip map={SEVERITY} value={severityBand(r.severity)} />,
    },
    {
      key: "is_critical",
      label: "Critical",
      render: (r) => (r.is_critical
        ? <StatusChip map={SEVERITY} value="Critical" />
        : <span className="text-muted-foreground text-xs">—</span>),
    },
    { key: "review_status", label: "Review", render: (r) => <StatusChip map={REVIEW_STATUS} value={r.review_status} /> },
    { key: "alert_type", label: "Type", render: (r) => <span className="text-muted-foreground">{r.alert_type || "—"}</span> },
    { key: "summary", label: "Summary", render: (r) => <span className="truncate">{r.summary || "—"}</span> },
    { key: "record_id", label: "Entity", render: (r) => (r.record_id ? <IdCode>{r.record_id}</IdCode> : <span className="text-muted-foreground text-xs">—</span>) },
    {
      key: "occurred_at",
      label: "Observed",
      render: (r) => <span className="text-muted-foreground text-xs">{r.occurred_at ? new Date(r.occurred_at).toLocaleDateString() : "—"}</span>,
    },
  ];

  return (
    <div>
      <ModulePageHeader module={MODULE} icon={Droplets} />
      <div className="mb-4 rounded-lg border border-border bg-card px-4 py-2.5 text-xs text-muted-foreground">
        Infrastructure summaries are sanitized — no sensitive vulnerability detail is stored.
      </div>
      <Tabs defaultValue="workspace">
        <TabsList className="mb-4 flex h-auto flex-wrap">
          <TabsTrigger value="workspace">Workspace</TabsTrigger>
          <TabsTrigger value="feed">Water + Power Feed</TabsTrigger>
          <TabsTrigger value="assets">Infrastructure Assets</TabsTrigger>
          <TabsTrigger value="alerts">Operational Alerts</TabsTrigger>
          <TabsTrigger value="risks">Continuity Risks</TabsTrigger>
        </TabsList>
        <TabsContent value="workspace">
          <IntelligenceWorkspace adapter={INTELLIGENCE_ADAPTERS.aguayluz} />
        </TabsContent>
        <TabsContent value="feed">
          <AguaYLuzFeedTab />
        </TabsContent>
        <TabsContent value="assets">
          <EntityLedger entityName="InfrastructureAssets" fields={assetFields} columns={assetColumns}
            searchKeys={["name", "asset_id", "municipality", "operator"]}
            filterDefs={[{ key: "asset_type", label: "Type", options: ASSET_TYPES }, { key: "status", label: "Status", options: ["Active", "Inactive", "Unknown", "UnderReview"] }]}
            addLabel="New Asset" emptyTitle="No assets" searchPlaceholder="Search assets…" />
        </TabsContent>
        <TabsContent value="alerts">
          <p className="mb-3 text-xs text-muted-foreground">
            AguaYLuz-PR&apos;s operational alert layer as exported to the federation
            (<code>alerts</code> stream). Read-only — these rows are a projection of the
            producer&apos;s export and are replaced on every hub ingest; adjudicate them in
            the producer, not here.
          </p>
          <EntityLedger entityName="GovernanceAlerts" columns={alertColumns} readOnly
            rowFilter={isAguayluzAlert}
            searchKeys={["summary", "module", "alert_type", "record_id"]}
            filterDefs={[
              { key: "module", label: "Module", options: ALERT_MODULES },
              { key: "review_status", label: "Review", options: ALERT_REVIEW_STATES },
            ]}
            emptyTitle="No AguaYLuz alerts"
            emptyDescription="No alerts from aguayluz-pr in the current aggregate. Run the Hub aggregate/ingest against an AguaYLuz federation export to populate them."
            searchPlaceholder="Search alerts…" />
        </TabsContent>
        <TabsContent value="risks">
          <EntityLedger entityName="ContinuityRisks" fields={riskFields} columns={riskColumns}
            searchKeys={["risk_id", "asset_id", "summary"]}
            filterDefs={[{ key: "risk_type", label: "Type", options: RISK_TYPES }, { key: "severity", label: "Severity", options: ["Low", "Medium", "High", "Critical"] }]}
            addLabel="New Risk" emptyTitle="No risks"
            emptyDescription="No continuity risks in the current aggregate. Risks are derived from AguaYLuz-PR water↔power dependencies and asset-anchored alerts; run the Hub aggregate/ingest to populate them."
            searchPlaceholder="Search risks…" />
        </TabsContent>
      </Tabs>
    </div>
  );
}
