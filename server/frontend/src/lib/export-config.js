// Federation export registry: every major ledger that supports CSV (+ GeoJSON where geospatial).
// Columns are ordered and preserve provenance fields (IDs, module, evidence tier, confidence,
// review status) where the schema provides them.

export const EXPORT_LEDGERS = [
  {
    entity: "UnifiedCases",
    label: "Unified Cases",
    module: "Ovnis-PR",
    geo: true,
    columns: ["case_id", "case_code", "program_id", "title", "case_type", "event_date", "municipality", "region", "latitude", "longitude", "confidence", "status", "sensitivity", "source_count"],
  },
  {
    entity: "UnifiedSources",
    label: "Unified Sources",
    module: "Hub",
    geo: false,
    columns: ["source_id", "program_id", "linked_case_id", "title", "source_type", "evidence_tier", "publisher", "publication_date", "url", "reliability", "verification_status", "sensitivity"],
  },
  {
    entity: "Contracts",
    label: "Contracts",
    module: "MoneySweep-PR",
    geo: false,
    columns: ["contract_id", "title", "agency", "municipality", "vendor_id", "award_amount", "award_date", "procurement_type", "funding_source", "source_url", "status"],
  },
  {
    entity: "Vendors",
    label: "Vendors",
    module: "MoneySweep-PR",
    geo: false,
    columns: ["vendor_id", "name", "normalized_name", "municipality", "linked_contract_count", "total_award_amount", "review_status"],
  },
  {
    entity: "InfrastructureAssets",
    label: "Infrastructure Assets",
    module: "AguaYLuz-PR",
    geo: true,
    columns: ["asset_id", "name", "asset_type", "municipality", "region", "latitude", "longitude", "operator", "owner_agency", "status", "sensitivity"],
  },
  {
    entity: "AirspaceEvents",
    label: "Airspace Events",
    module: "Skywatcher-PR",
    geo: true,
    columns: ["event_id", "title", "event_date", "municipality", "region", "latitude", "longitude", "event_type", "source_id", "confidence", "status"],
  },
  {
    entity: "GraphNodes",
    label: "Graph Nodes",
    module: "Spiderweb-PR",
    geo: true,
    columns: ["node_id", "label", "node_type", "linked_program_id", "linked_case_id", "linked_source_id", "municipality", "latitude", "longitude", "confidence", "sensitivity"],
  },
  {
    entity: "GraphEdges",
    label: "Graph Edges",
    module: "Spiderweb-PR",
    geo: false,
    columns: ["edge_id", "source_node_id", "target_node_id", "relationship_type", "evidence_tier", "confidence", "source_id", "status", "sensitivity"],
  },
  {
    entity: "FederationTasks",
    label: "Federation Tasks",
    module: "Hub",
    geo: false,
    columns: ["task_id", "program_id", "title", "task_type", "priority", "status", "assigned_to", "due_date", "sensitivity"],
  },
];

export const EXPORTS_STATUS = {
  Generated: "bg-blue-500/15 text-blue-300 border-blue-500/30",
  Downloaded: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  Archived: "bg-slate-500/15 text-slate-300 border-slate-500/30",
  Failed: "bg-red-500/15 text-red-300 border-red-500/30",
};