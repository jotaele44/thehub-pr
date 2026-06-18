import React from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import ModulePageHeader from "@/components/shared/ModulePageHeader";
import EntityLedger from "@/components/shared/EntityLedger";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import { Radar } from "lucide-react";
import { MODULES } from "@/lib/federation";
import { CONFIDENCE, REVIEW_STATUS, VERIFICATION, GENERIC_STATUS } from "@/lib/chips";

const MODULE = MODULES.find((m) => m.name === "Ovnis-PR");
const PATTERN_TYPES = ["Light", "Object", "Formation", "Maneuver", "Sound", "Electromagnetic", "RepeatedLocation", "TimeCluster", "Other"];

export default function Ovnis() {
  const patternFields = [
    { key: "pattern_id", label: "Pattern ID", required: true },
    { key: "linked_case_id", label: "Linked Case ID", required: true },
    { key: "pattern_type", label: "Pattern Type", type: "select", options: PATTERN_TYPES, required: true },
    { key: "confidence", label: "Confidence", type: "select", options: ["Low", "Medium", "High"], required: true },
    { key: "status", label: "Status", type: "select", options: ["Proposed", "Reviewing", "Accepted", "Disputed", "Rejected"], required: true },
    { key: "source_id", label: "Source ID" },
    { key: "description", label: "Description", type: "textarea" },
  ];
  const patternColumns = [
    { key: "pattern_id", label: "ID", render: (r) => <IdCode>{r.pattern_id}</IdCode> },
    { key: "pattern_type", label: "Type", render: (r) => <span className="font-medium">{r.pattern_type}</span> },
    { key: "linked_case_id", label: "Case", render: (r) => <IdCode>{r.linked_case_id}</IdCode> },
    { key: "confidence", label: "Confidence", render: (r) => <StatusChip map={CONFIDENCE} value={r.confidence} /> },
    { key: "status", label: "Status", render: (r) => <StatusChip map={REVIEW_STATUS} value={r.status} /> },
  ];

  const witnessFields = [
    { key: "witness_report_id", label: "Report ID", required: true },
    { key: "linked_case_id", label: "Linked Case ID", required: true },
    { key: "witness_count", label: "Witness Count", type: "number" },
    { key: "privacy_status", label: "Privacy Status", type: "select", options: ["Sanitized", "Restricted", "Excluded"], required: true },
    { key: "verification_status", label: "Verification", type: "select", options: ["Unreviewed", "Verified", "Disputed", "Rejected"], required: true },
    { key: "testimony_summary", label: "Sanitized Testimony Summary", type: "textarea" },
  ];
  const witnessColumns = [
    { key: "witness_report_id", label: "ID", render: (r) => <IdCode>{r.witness_report_id}</IdCode> },
    { key: "linked_case_id", label: "Case", render: (r) => <IdCode>{r.linked_case_id}</IdCode> },
    { key: "witness_count", label: "Witnesses" },
    { key: "privacy_status", label: "Privacy", render: (r) => <StatusChip map={GENERIC_STATUS} value={r.privacy_status} /> },
    { key: "verification_status", label: "Verification", render: (r) => <StatusChip map={VERIFICATION} value={r.verification_status} /> },
  ];

  return (
    <div>
      <ModulePageHeader module={MODULE} icon={Radar} />
      <div className="mb-4 rounded-lg border border-border bg-card px-4 py-2.5 text-xs text-muted-foreground">
        Witness data is stored as sanitized summaries only — no raw private testimony. Default tier T3.
      </div>
      <Tabs defaultValue="patterns">
        <TabsList className="mb-4">
          <TabsTrigger value="patterns">Pattern Observations</TabsTrigger>
          <TabsTrigger value="witness">Witness Reports</TabsTrigger>
        </TabsList>
        <TabsContent value="patterns">
          <EntityLedger entityName="PatternObservations" fields={patternFields} columns={patternColumns}
            searchKeys={["pattern_id", "linked_case_id", "description"]}
            filterDefs={[{ key: "pattern_type", label: "Type", options: PATTERN_TYPES }, { key: "confidence", label: "Confidence", options: ["Low", "Medium", "High"] }]}
            addLabel="New Pattern" emptyTitle="No patterns" searchPlaceholder="Search patterns…" />
        </TabsContent>
        <TabsContent value="witness">
          <EntityLedger entityName="WitnessReports" fields={witnessFields} columns={witnessColumns}
            searchKeys={["witness_report_id", "linked_case_id"]}
            filterDefs={[{ key: "privacy_status", label: "Privacy", options: ["Sanitized", "Restricted", "Excluded"] }, { key: "verification_status", label: "Verification", options: ["Unreviewed", "Verified", "Disputed", "Rejected"] }]}
            addLabel="New Report" emptyTitle="No witness reports" searchPlaceholder="Search reports…" />
        </TabsContent>
      </Tabs>
    </div>
  );
}