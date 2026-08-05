import React from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import ModulePageHeader from "@/components/shared/ModulePageHeader";
import EntityLedger from "@/components/shared/EntityLedger";
import ModuleMapTab from "@/components/shared/ModuleMapTab";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import { Radio } from "lucide-react";
import { MODULES, REGIONS } from "@/lib/federation";
import { GENERIC_STATUS, CONFIDENCE } from "@/lib/chips";

const MODULE = MODULES.find((m) => m.name === "Centinelas-PR");
const MATTER_STATUSES = ["New", "Reviewing", "Routed", "Officialized", "Dismissed"];
const ROUTE_TARGETS = ["MoneySweep-PR", "Spiderweb-PR", "AguaYLuz-PR", "Ovnis-PR", "Skywatcher-PR", "Hub"];

export default function Centinelas() {
  const matterFields = [
    { key: "matter_id", label: "Matter ID", required: true },
    { key: "title", label: "Title", required: true, full: true },
    { key: "entity_type", label: "Type" },
    { key: "municipality", label: "Municipality" },
    { key: "region", label: "Region", type: "select", options: REGIONS },
    { key: "routed_to", label: "Routed To", type: "select", options: ROUTE_TARGETS },
    { key: "source_id", label: "Source ID" },
    { key: "confidence", label: "Confidence", type: "select", options: ["Low", "Medium", "High"], required: true },
    { key: "status", label: "Status", type: "select", options: MATTER_STATUSES, required: true },
    { key: "summary", label: "Summary", type: "textarea" },
  ];
  const matterColumns = [
    { key: "matter_id", label: "ID", render: (r) => <IdCode>{r.matter_id}</IdCode> },
    { key: "title", label: "Title", render: (r) => <span className="font-medium">{r.title}</span> },
    { key: "municipality", label: "Municipality" },
    { key: "routed_to", label: "Routed To", render: (r) => <span className="text-muted-foreground">{r.routed_to}</span> },
    { key: "confidence", label: "Confidence", render: (r) => <StatusChip map={CONFIDENCE} value={r.confidence} /> },
    { key: "status", label: "Status", render: (r) => <StatusChip map={GENERIC_STATUS} value={r.status} /> },
  ];

  return (
    <div>
      <ModulePageHeader module={MODULE} icon={Radio} />
      <Tabs defaultValue="matters">
        <TabsList className="mb-4">
          <TabsTrigger value="matters">Public Matters</TabsTrigger>
          <TabsTrigger value="map">Map View</TabsTrigger>
        </TabsList>
        <TabsContent value="matters">
          <EntityLedger entityName="PublicMatters" fields={matterFields} columns={matterColumns}
            searchKeys={["title", "matter_id", "municipality"]}
            filterDefs={[{ key: "status", label: "Status", options: MATTER_STATUSES }, { key: "confidence", label: "Confidence", options: ["Low", "Medium", "High"] }]}
            addLabel="New Matter" emptyTitle="No public matters"
            emptyDescription="Centinelas-PR public matters populate here after `hub ingest` loads its canonical export."
            searchPlaceholder="Search matters…" />
        </TabsContent>
        <TabsContent value="map">
          <ModuleMapTab
            entityName="PublicMatters"
            buildPoint={(r) => ({
              id: r.id,
              lat: r.latitude,
              lon: r.longitude,
              title: r.title || r.name,
              subtitle: [r.entity_type, r.municipality].filter(Boolean).join(" · "),
            })}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
