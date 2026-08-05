import React from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import ModulePageHeader from "@/components/shared/ModulePageHeader";
import EntityLedger from "@/components/shared/EntityLedger";
import ModuleMapTab from "@/components/shared/ModuleMapTab";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import { Plane } from "lucide-react";
import { MODULES, REGIONS } from "@/lib/federation";
import { GENERIC_STATUS, CONFIDENCE, REVIEW_STATUS } from "@/lib/chips";

const MODULE = MODULES.find((m) => m.name === "Skywatcher-PR");
const EVENT_TYPES = ["Aviation", "Launch", "Satellite", "Drone", "MilitaryExercise", "WeatherBalloon", "SensorReport", "Other"];
const CORR_TYPES = ["Temporal", "Spatial", "TemporalSpatial", "SourceBased", "RuledOut", "Other"];

export default function Skywatcher() {
  const eventFields = [
    { key: "event_id", label: "Event ID", required: true },
    { key: "title", label: "Title", required: true, full: true },
    { key: "event_type", label: "Type", type: "select", options: EVENT_TYPES, required: true },
    { key: "event_date", label: "Event Date", type: "date" },
    { key: "date_precision", label: "Date Precision", type: "select", options: ["Exact", "Day", "Month", "Year", "Undated"], required: true },
    { key: "municipality", label: "Municipality" },
    { key: "region", label: "Region", type: "select", options: REGIONS },
    { key: "latitude", label: "Latitude", type: "number" },
    { key: "longitude", label: "Longitude", type: "number" },
    { key: "source_id", label: "Source ID" },
    { key: "confidence", label: "Confidence", type: "select", options: ["Low", "Medium", "High"], required: true },
    { key: "status", label: "Status", type: "select", options: ["New", "Reviewing", "Correlated", "RuledOut", "Archived"], required: true },
    { key: "summary", label: "Summary", type: "textarea" },
  ];
  const eventColumns = [
    { key: "event_id", label: "ID", render: (r) => <IdCode>{r.event_id}</IdCode> },
    { key: "title", label: "Title", render: (r) => <span className="font-medium">{r.title}</span> },
    { key: "event_type", label: "Type", render: (r) => <span className="text-muted-foreground">{r.event_type}</span> },
    { key: "municipality", label: "Municipality" },
    { key: "confidence", label: "Confidence", render: (r) => <StatusChip map={CONFIDENCE} value={r.confidence} /> },
    { key: "status", label: "Status", render: (r) => <StatusChip map={GENERIC_STATUS} value={r.status} /> },
  ];

  const corrFields = [
    { key: "review_id", label: "Review ID", required: true },
    { key: "airspace_event_id", label: "Airspace Event ID", required: true },
    { key: "linked_ovnis_case_id", label: "Linked Ovnis Case ID" },
    { key: "correlation_type", label: "Correlation Type", type: "select", options: CORR_TYPES, required: true },
    { key: "time_window_minutes", label: "Time Window (min)", type: "number" },
    { key: "distance_km", label: "Distance (km)", type: "number" },
    { key: "confidence", label: "Confidence", type: "select", options: ["Low", "Medium", "High"], required: true },
    { key: "status", label: "Status", type: "select", options: ["Proposed", "Reviewing", "Accepted", "Rejected", "Inconclusive"], required: true },
    { key: "rationale", label: "Rationale", type: "textarea", required: true },
  ];
  const corrColumns = [
    { key: "review_id", label: "ID", render: (r) => <IdCode>{r.review_id}</IdCode> },
    { key: "airspace_event_id", label: "Event", render: (r) => <IdCode>{r.airspace_event_id}</IdCode> },
    { key: "correlation_type", label: "Type", render: (r) => <span className="font-medium">{r.correlation_type}</span> },
    { key: "confidence", label: "Confidence", render: (r) => <StatusChip map={CONFIDENCE} value={r.confidence} /> },
    { key: "status", label: "Status", render: (r) => <StatusChip map={REVIEW_STATUS} value={r.status} /> },
  ];

  return (
    <div>
      <ModulePageHeader module={MODULE} icon={Plane} />
      <Tabs defaultValue="events">
        <TabsList className="mb-4">
          <TabsTrigger value="events">Airspace Events</TabsTrigger>
          <TabsTrigger value="map">Map View</TabsTrigger>
          <TabsTrigger value="corr">Correlation Reviews</TabsTrigger>
        </TabsList>
        <TabsContent value="events">
          <EntityLedger entityName="AirspaceEvents" fields={eventFields} columns={eventColumns}
            searchKeys={["title", "event_id", "municipality"]}
            filterDefs={[{ key: "event_type", label: "Type", options: EVENT_TYPES }, { key: "status", label: "Status", options: ["New", "Reviewing", "Correlated", "RuledOut", "Archived"] }]}
            addLabel="New Event" emptyTitle="No events"
            emptyDescription="Skywatcher-PR's current export is synthetic-only — real events populate once it ships a live FR24 capture."
            searchPlaceholder="Search events…" />
        </TabsContent>
        <TabsContent value="map">
          <ModuleMapTab
            entityName="AirspaceEvents"
            buildPoint={(r) => ({
              id: r.id,
              lat: r.latitude,
              lon: r.longitude,
              title: r.title,
              subtitle: [r.event_type, r.municipality].filter(Boolean).join(" · "),
            })}
          />
        </TabsContent>
        <TabsContent value="corr">
          <EntityLedger entityName="CorrelationReviews" fields={corrFields} columns={corrColumns}
            searchKeys={["review_id", "airspace_event_id", "rationale"]}
            filterDefs={[{ key: "correlation_type", label: "Type", options: CORR_TYPES }, { key: "confidence", label: "Confidence", options: ["Low", "Medium", "High"] }]}
            addLabel="New Review" emptyTitle="No reviews"
            emptyDescription="Correlation review records aren't in the canonical federation export yet — data pending richer Skywatcher-PR intake."
            searchPlaceholder="Search reviews…" />
        </TabsContent>
      </Tabs>
    </div>
  );
}