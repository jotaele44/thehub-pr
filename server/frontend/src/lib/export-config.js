// Exportable federation ledgers + export-status chip map.

const GREEN = "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
const BLUE = "bg-sky-500/15 text-sky-300 border-sky-500/30";
const RED = "bg-red-500/15 text-red-300 border-red-500/30";
const SLATE = "bg-slate-500/15 text-slate-300 border-slate-500/30";

export const EXPORTS_STATUS = {
  Generated: BLUE,
  Downloaded: GREEN,
  Failed: RED,
  Expired: SLATE,
};

// Each ledger: entity (federation entity name), label, owning module,
// geo (GeoJSON exportable), and preferred CSV column order (undefined = all).
export const EXPORT_LEDGERS = [
  {
    entity: "UnifiedCases",
    label: "Unified Cases",
    module: "Hub",
    geo: true,
    columns: ["case_id", "case_code", "program_id", "title", "case_type", "status", "event_date", "date_precision", "municipality", "region", "latitude", "longitude", "confidence", "sensitivity", "summary_public"],
  },
  {
    entity: "UnifiedSources",
    label: "Unified Sources",
    module: "Hub",
    geo: false,
    columns: ["source_id", "program_id", "title", "source_type", "evidence_tier", "reliability", "verification_status", "sensitivity", "url"],
  },
  {
    entity: "GraphNodes",
    label: "Graph Nodes",
    module: "Spiderweb-PR",
    geo: true,
    columns: ["node_id", "label", "node_type", "confidence", "sensitivity", "municipality", "latitude", "longitude", "summary"],
  },
  {
    entity: "GraphEdges",
    label: "Graph Edges",
    module: "Spiderweb-PR",
    geo: false,
    columns: ["edge_id", "source_node_id", "target_node_id", "relationship_type", "evidence_tier", "confidence", "status", "sensitivity"],
  },
  {
    entity: "AirspaceEvents",
    label: "Airspace Events",
    module: "Skywatcher-PR",
    geo: true,
    columns: ["event_id", "event_type", "event_date", "region", "municipality", "latitude", "longitude", "confidence", "status", "summary"],
  },
  {
    entity: "InfrastructureAssets",
    label: "Infrastructure Assets",
    module: "AguaYLuz-PR",
    geo: true,
    columns: ["asset_id", "name", "asset_type", "municipality", "latitude", "longitude", "status", "sensitivity"],
  },
  {
    entity: "ContinuityRisks",
    label: "Continuity Risks",
    module: "AguaYLuz-PR",
    geo: false,
    columns: ["risk_id", "risk_type", "severity", "confidence", "status", "municipality", "summary"],
  },
  {
    entity: "Contracts",
    label: "Contracts",
    module: "MoneySweep-PR",
    geo: false,
    columns: ["contract_id", "title", "agency", "vendor_name", "amount", "award_date", "municipality", "status", "sensitivity"],
  },
  {
    entity: "Vendors",
    label: "Vendors",
    module: "MoneySweep-PR",
    geo: false,
    columns: ["vendor_id", "name", "status", "review_status", "municipality"],
  },
  {
    entity: "AnomalyFlags",
    label: "Anomaly Flags",
    module: "Ovnis-PR",
    geo: true,
    columns: ["anomaly_id", "severity", "confidence", "review_status", "municipality", "region", "latitude", "longitude", "summary"],
  },
  {
    entity: "CrossoverLinks",
    label: "Crossover Links",
    module: "Hub",
    geo: false,
    columns: ["crossover_id", "source_module", "source_record_id", "target_module", "target_record_id", "status", "correlation_type", "confidence_score", "evidence_tier", "rationale"],
  },
  {
    entity: "FederationTasks",
    label: "Federation Tasks",
    module: "Hub",
    geo: false,
    columns: ["task_id", "program_id", "title", "task_type", "priority", "status", "sensitivity", "assigned_to", "due_date", "summary"],
  },
];
