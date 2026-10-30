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
import {
  GENERIC_STATUS, SENSITIVITY, SEVERITY, CONFIDENCE, REVIEW_STATUS,
  OUTDOOR_LEVEL, OUTDOOR_STATE, RIP_RISK, HEAT_BAND, UV_CATEGORY, AQI_CATEGORY,
} from "@/lib/chips";

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

// GovernanceAlerts (and any federation-wide collection) holds every producer's rows;
// scope AguaYLuz's read-only tabs to the rows aguayluz-pr contributed.
const isAguayluzRow = (row) => (row?._producers || []).includes("aguayluz-pr");

// OutdoorConditions is projected from aguayluz-pr's `outdoor_condition` entities
// (`project_outdoor_conditions` in src/hub/ingest.py): one row per municipio, every
// component's value beside its `<component>_state`.
const OUTDOOR_LEVELS = Object.keys(OUTDOOR_LEVEL);
const RIP_RISKS = Object.keys(RIP_RISK);
const HEAT_BANDS = Object.keys(HEAT_BAND);
const present = (v) => v !== undefined && v !== null && v !== "";

// A cell without a value says why (NOT_COVERED, SOURCE_FAILED, …) instead of going
// blank: an empty cell would read as "all clear", which missing data never is. A
// value carried past its source's freshness keeps a STALE chip beside it.
function OutdoorCell({ state, children }) {
  if (!present(children)) return <StatusChip map={OUTDOOR_STATE} value={state} />;
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
      {children}
      {state === "STALE" && <StatusChip map={OUTDOOR_STATE} value="STALE" />}
    </span>
  );
}

// Some PR buoys report wind only; say so rather than showing a bare dash.
const buoyText = (r) => [
  present(r.wave_height_ft) && `${r.wave_height_ft} ft`,
  present(r.water_temp_f) && `${r.water_temp_f} °F`,
].filter(Boolean).join(" · ") || (present(r.wind_speed_kt) ? `wind ${r.wind_speed_kt} kt, no waves` : "no waves reported");

const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
const outdoorAlerts = (r) => [
  r.nws_alerts,
  r.marine_alerts,
  r.storms && `Storm: ${r.storms}`,
  r.closures ? `${plural(r.closures, "closure")} (${r.closure_assets})` : null,
].filter(Boolean).join(" · ");

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

  const outdoorColumns = [
    { key: "municipality", label: "Municipio", render: (r) => <span className="font-medium">{r.municipality}</span> },
    {
      key: "level",
      label: "Level",
      render: (r) => <span title={r.driver_summary || undefined}><StatusChip map={OUTDOOR_LEVEL} value={r.level} /></span>,
    },
    {
      key: "rip_current_risk",
      label: "Rip risk",
      render: (r) => (
        <OutdoorCell state={r.rip_current_state}>
          {present(r.rip_current_risk) ? <StatusChip map={RIP_RISK} value={r.rip_current_risk} /> : null}
        </OutdoorCell>
      ),
    },
    {
      key: "surf_ft",
      label: "Surf",
      render: (r) => <OutdoorCell state={r.rip_current_state}>{present(r.surf_ft) ? `${r.surf_ft} ft` : null}</OutdoorCell>,
    },
    {
      key: "wave_height_ft",
      label: "Nearest buoy",
      render: (r) => (
        <OutdoorCell state={r.sea_state_state}>
          {present(r.buoy_station) ? (
            <span title={`Buoy ${r.buoy_station}, ${r.buoy_distance_km} km away (offshore point observation)`}>
              {buoyText(r)}
            </span>
          ) : null}
        </OutdoorCell>
      ),
    },
    {
      key: "uv_index",
      label: "UV",
      render: (r) => (
        <OutdoorCell state={r.uv_state}>
          {present(r.uv_index) ? <>{r.uv_index} <StatusChip map={UV_CATEGORY} value={r.uv_category} /></> : null}
        </OutdoorCell>
      ),
    },
    {
      key: "heat_band",
      label: "Heat",
      render: (r) => (
        <OutdoorCell state={r.heat_state}>
          {present(r.heat_band) ? (
            <span title={present(r.heat_index_max_f) ? `Max heat index ${r.heat_index_max_f} °F (next 24 h)` : undefined}>
              <StatusChip map={HEAT_BAND} value={r.heat_band} />
            </span>
          ) : null}
        </OutdoorCell>
      ),
    },
    {
      key: "aqi",
      label: "AQI",
      render: (r) => (
        <OutdoorCell state={r.air_quality_state}>
          {present(r.aqi) ? <>{r.aqi} <StatusChip map={AQI_CATEGORY} value={r.aqi_category} /></> : null}
        </OutdoorCell>
      ),
    },
    {
      key: "beach_advisories",
      label: "Beach",
      render: (r) => (
        <OutdoorCell state={r.beach_water_quality_state}>
          {r.beach_advisories ? <span title={r.beach_advisory_names}>{r.beach_advisories} {r.beach_advisories === 1 ? "advisory" : "advisories"}</span> : null}
        </OutdoorCell>
      ),
    },
    {
      key: "river_flood_category",
      label: "River",
      render: (r) => (
        <OutdoorCell state={r.river_flood_state}>
          {present(r.river_flood_category)
            ? `${r.river_flood_category} flood stage`
            : r.river_flood_state === "REPORTED" ? "No gauge in flood" : null}
        </OutdoorCell>
      ),
    },
    {
      key: "rain_24h_max_in",
      label: "Rain 24 h",
      render: (r) => (
        <OutdoorCell state={r.rainfall_24h_state}>
          {present(r.rain_24h_max_in) ? <span title={`Stage IV, ${r.rain_date}; mean ${r.rain_24h_mean_in} in`}>{r.rain_24h_max_in} in max</span> : null}
        </OutdoorCell>
      ),
    },
    {
      key: "nws_alerts",
      label: "Alerts & closures",
      render: (r) => <OutdoorCell state={r.nws_alerts_state}><span className="truncate">{outdoorAlerts(r) || null}</span></OutdoorCell>,
    },
    {
      key: "as_of",
      label: "As of",
      render: (r) => <span className="text-muted-foreground text-xs">{r.as_of ? new Date(r.as_of).toLocaleString() : "—"}</span>,
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
          <TabsTrigger value="outdoor">Outdoor Conditions</TabsTrigger>
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
            rowFilter={isAguayluzRow}
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
        <TabsContent value="outdoor">
          <p className="mb-3 text-xs text-muted-foreground">
            Current outdoor conditions per municipio, composed by AguaYLuz-PR from official
            public sources (NWS surf-zone, marine, alert and gridpoint products, NDBC buoys,
            EPA UV, AirNow, DRNA beach monitoring, NWPS gauges, Stage IV rainfall, NHC, USGS
            and USFS El Yunque orders). Conditions context, not safety advice. A cell with no
            value shows why — not covered, stale, source failed or not configured — because
            missing data is never &ldquo;all clear&rdquo;. Read-only; replaced on every hub ingest.
          </p>
          <EntityLedger entityName="OutdoorConditions" columns={outdoorColumns} readOnly
            rowFilter={isAguayluzRow}
            searchKeys={["municipality", "driver_summary", "nws_alerts", "marine_alerts", "closure_assets"]}
            filterDefs={[
              { key: "level", label: "Level", options: OUTDOOR_LEVELS },
              { key: "rip_current_risk", label: "Rip risk", options: RIP_RISKS },
              { key: "heat_band", label: "Heat", options: HEAT_BANDS },
            ]}
            emptyTitle="No outdoor conditions"
            emptyDescription="No outdoor-condition rows from aguayluz-pr in the current aggregate. Run the Hub aggregate/ingest against an AguaYLuz federation export that includes data/outdoor_conditions.jsonl."
            searchPlaceholder="Search municipios, drivers, alerts…" />
        </TabsContent>
      </Tabs>
    </div>
  );
}
