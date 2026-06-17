import React from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import ModulePageHeader from "@/components/shared/ModulePageHeader";
import EntityLedger from "@/components/shared/EntityLedger";
import ModuleMapTab from "@/components/shared/ModuleMapTab";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import { Network } from "lucide-react";
import { MODULES } from "@/lib/federation";
import { CONFIDENCE, SENSITIVITY, TIER, REVIEW_STATUS } from "@/lib/chips";

const MODULE = MODULES.find((m) => m.name === "Spiderweb-PR");
const NODE_TYPES = ["Program", "Case", "Source", "Organization", "Person", "Location", "Event", "Asset", "Vendor"];
const REL_TYPES = ["RelatedTo", "LocatedAt", "FundedBy", "OperatedBy", "ReportedBy", "CorrelatesWith", "Contradicts", "Supports", "DependsOn"];
const TIERS = ["T1", "T2", "T3", "T4"];

export default function Spiderweb() {
  const nodeFields = [
    { key: "node_id", label: "Node ID", required: true },
    { key: "label", label: "Label", required: true, full: true },
    { key: "node_type", label: "Type", type: "select", options: NODE_TYPES, required: true },
    { key: "municipality", label: "Municipality" },
    { key: "latitude", label: "Latitude", type: "number" },
    { key: "longitude", label: "Longitude", type: "number" },
    { key: "confidence", label: "Confidence", type: "select", options: ["Low", "Medium", "High"], required: true },
    { key: "sensitivity", label: "Sensitivity", type: "select", options: ["Public", "Internal", "Restricted"], required: true },
    { key: "summary", label: "Summary", type: "textarea" },
  ];
  const nodeColumns = [
    { key: "node_id", label: "ID", render: (r) => <IdCode>{r.node_id}</IdCode> },
    { key: "label", label: "Label", render: (r) => <span className="font-medium">{r.label}</span> },
    { key: "node_type", label: "Type", render: (r) => <span className="text-muted-foreground">{r.node_type}</span> },
    { key: "confidence", label: "Confidence", render: (r) => <StatusChip map={CONFIDENCE} value={r.confidence} /> },
    { key: "sensitivity", label: "Sensitivity", render: (r) => <StatusChip map={SENSITIVITY} value={r.sensitivity} /> },
  ];

  const edgeFields = [
    { key: "edge_id", label: "Edge ID", required: true },
    { key: "source_node_id", label: "Source Node ID", required: true },
    { key: "target_node_id", label: "Target Node ID", required: true },
    { key: "relationship_type", label: "Relationship", type: "select", options: REL_TYPES, required: true },
    { key: "evidence_tier", label: "Evidence Tier", type: "select", options: TIERS, required: true },
    { key: "confidence", label: "Confidence", type: "select", options: ["Low", "Medium", "High"], required: true },
    { key: "status", label: "Status", type: "select", options: ["Proposed", "Reviewing", "Accepted", "Disputed", "Rejected"], required: true },
    { key: "sensitivity", label: "Sensitivity", type: "select", options: ["Public", "Internal", "Restricted"], required: true },
    { key: "rationale", label: "Rationale", type: "textarea", required: true },
  ];
  const edgeColumns = [
    { key: "edge_id", label: "ID", render: (r) => <IdCode>{r.edge_id}</IdCode> },
    { key: "source_node_id", label: "Source", render: (r) => <IdCode>{r.source_node_id}</IdCode> },
    { key: "target_node_id", label: "Target", render: (r) => <IdCode>{r.target_node_id}</IdCode> },
    { key: "relationship_type", label: "Relationship", render: (r) => <span className="text-muted-foreground">{r.relationship_type}</span> },
    { key: "evidence_tier", label: "Tier", render: (r) => <StatusChip map={TIER} value={r.evidence_tier} /> },
    { key: "status", label: "Status", render: (r) => <StatusChip map={REVIEW_STATUS} value={r.status} /> },
  ];

  return (
    <div>
      <ModulePageHeader module={MODULE} icon={Network} />
      <Tabs defaultValue="nodes">
        <TabsList className="mb-4">
          <TabsTrigger value="nodes">Graph Nodes</TabsTrigger>
          <TabsTrigger value="map">Map View</TabsTrigger>
          <TabsTrigger value="edges">Graph Edges</TabsTrigger>
        </TabsList>
        <TabsContent value="nodes">
          <EntityLedger entityName="GraphNodes" fields={nodeFields} columns={nodeColumns}
            searchKeys={["label", "node_id", "municipality"]}
            filterDefs={[{ key: "node_type", label: "Type", options: NODE_TYPES }, { key: "confidence", label: "Confidence", options: ["Low", "Medium", "High"] }]}
            addLabel="New Node" emptyTitle="No nodes" searchPlaceholder="Search nodes…" />
        </TabsContent>
        <TabsContent value="map">
          <ModuleMapTab
            entityName="GraphNodes"
            buildPoint={(r) => ({
              id: r.id,
              lat: r.latitude,
              lon: r.longitude,
              title: r.label,
              subtitle: [r.node_type, r.municipality].filter(Boolean).join(" · "),
            })}
          />
        </TabsContent>
        <TabsContent value="edges">
          <EntityLedger entityName="GraphEdges" fields={edgeFields} columns={edgeColumns}
            searchKeys={["edge_id", "source_node_id", "target_node_id", "rationale"]}
            filterDefs={[{ key: "relationship_type", label: "Relationship", options: REL_TYPES }, { key: "evidence_tier", label: "Tier", options: TIERS }]}
            addLabel="New Edge" emptyTitle="No edges" searchPlaceholder="Search edges…" />
        </TabsContent>
      </Tabs>
    </div>
  );
}