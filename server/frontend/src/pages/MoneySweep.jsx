import React from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import ModulePageHeader from "@/components/shared/ModulePageHeader";
import EntityLedger from "@/components/shared/EntityLedger";
import MoneySweepFeedTab from "@/components/feed/MoneySweepFeedTab";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import { Banknote } from "lucide-react";
import { MODULES } from "@/lib/federation";
import { GENERIC_STATUS, SEVERITY, CONFIDENCE, REVIEW_STATUS } from "@/lib/chips";

const MODULE = MODULES.find((m) => m.name === "MoneySweep-PR");
const PROC_TYPES = ["Competitive", "Emergency", "SoleSource", "Grant", "Unknown", "Other"];
const FLAG_TYPES = ["DuplicateVendor", "UnusualAmount", "EmergencyPattern", "SoleSourcePattern", "MissingData", "RepeatedAward", "TimingAnomaly", "Other"];

const fmtMoney = (n) => (n || n === 0) ? `$${Number(n).toLocaleString()}` : "—";

export default function MoneySweep() {
  const contractFields = [
    { key: "contract_id", label: "Contract ID", required: true },
    { key: "title", label: "Title", required: true, full: true },
    { key: "agency", label: "Agency", required: true },
    { key: "municipality", label: "Municipality" },
    { key: "vendor_id", label: "Vendor ID" },
    { key: "award_amount", label: "Award Amount", type: "number" },
    { key: "award_date", label: "Award Date", type: "date" },
    { key: "procurement_type", label: "Procurement", type: "select", options: PROC_TYPES },
    { key: "funding_source", label: "Funding Source" },
    { key: "source_url", label: "Source URL", full: true },
    { key: "status", label: "Status", type: "select", options: ["New", "Reviewing", "Flagged", "Cleared", "Archived"], required: true },
    { key: "summary", label: "Summary", type: "textarea" },
  ];
  const contractColumns = [
    { key: "contract_id", label: "ID", render: (r) => <IdCode>{r.contract_id}</IdCode> },
    { key: "title", label: "Title", render: (r) => <span className="font-medium">{r.title}</span> },
    { key: "agency", label: "Agency", render: (r) => <span className="text-muted-foreground">{r.agency}</span> },
    { key: "award_amount", label: "Amount", render: (r) => <span className="font-mono-id text-xs">{fmtMoney(r.award_amount)}</span> },
    { key: "procurement_type", label: "Procurement" },
    { key: "status", label: "Status", render: (r) => <StatusChip map={GENERIC_STATUS} value={r.status} /> },
  ];

  const vendorFields = [
    { key: "vendor_id", label: "Vendor ID", required: true },
    { key: "name", label: "Name", required: true, full: true },
    { key: "normalized_name", label: "Normalized Name", required: true, full: true },
    { key: "municipality", label: "Municipality" },
    { key: "linked_contract_count", label: "Contract Count", type: "number" },
    { key: "total_award_amount", label: "Total Awards", type: "number" },
    { key: "review_status", label: "Review Status", type: "select", options: ["Unreviewed", "Reviewing", "Reviewed", "NeedsFollowup"], required: true },
    { key: "risk_notes", label: "Risk Notes", type: "textarea" },
  ];
  const vendorColumns = [
    { key: "vendor_id", label: "ID", render: (r) => <IdCode>{r.vendor_id}</IdCode> },
    { key: "name", label: "Name", render: (r) => <span className="font-medium">{r.name}</span> },
    { key: "linked_contract_count", label: "Contracts" },
    { key: "total_award_amount", label: "Total", render: (r) => <span className="font-mono-id text-xs">{fmtMoney(r.total_award_amount)}</span> },
    { key: "review_status", label: "Review", render: (r) => <StatusChip map={REVIEW_STATUS} value={r.review_status} /> },
  ];

  const flagFields = [
    { key: "flag_id", label: "Flag ID", required: true },
    { key: "contract_id", label: "Contract ID", required: true },
    { key: "flag_type", label: "Flag Type", type: "select", options: FLAG_TYPES, required: true },
    { key: "severity", label: "Severity", type: "select", options: ["Low", "Medium", "High", "Critical"], required: true },
    { key: "confidence", label: "Confidence", type: "select", options: ["Low", "Medium", "High"], required: true },
    { key: "review_status", label: "Review Status", type: "select", options: ["Proposed", "Reviewing", "Accepted", "Rejected", "FalsePositive"], required: true },
    { key: "source_id", label: "Source ID" },
    { key: "rationale", label: "Rationale", type: "textarea", required: true },
    { key: "false_positive_reason", label: "False Positive Reason", type: "textarea" },
  ];
  const flagColumns = [
    { key: "flag_id", label: "ID", render: (r) => <IdCode>{r.flag_id}</IdCode> },
    { key: "contract_id", label: "Contract", render: (r) => <IdCode>{r.contract_id}</IdCode> },
    { key: "flag_type", label: "Type", render: (r) => <span className="font-medium">{r.flag_type}</span> },
    { key: "severity", label: "Severity", render: (r) => <StatusChip map={SEVERITY} value={r.severity} /> },
    { key: "confidence", label: "Confidence", render: (r) => <StatusChip map={CONFIDENCE} value={r.confidence} /> },
    { key: "review_status", label: "Review", render: (r) => <StatusChip map={REVIEW_STATUS} value={r.review_status} /> },
  ];

  return (
    <div>
      <ModulePageHeader module={MODULE} icon={Banknote} />
      <Tabs defaultValue="feed">
        <TabsList className="mb-4">
          <TabsTrigger value="feed">Procurement + Funding Feed</TabsTrigger>
          <TabsTrigger value="contracts">Contracts</TabsTrigger>
          <TabsTrigger value="vendors">Vendors</TabsTrigger>
          <TabsTrigger value="flags">Anomaly Flags</TabsTrigger>
        </TabsList>
        <TabsContent value="feed">
          <MoneySweepFeedTab />
        </TabsContent>
        <TabsContent value="contracts">
          <EntityLedger entityName="Contracts" fields={contractFields} columns={contractColumns}
            searchKeys={["title", "contract_id", "agency", "municipality"]}
            filterDefs={[{ key: "procurement_type", label: "Procurement", options: PROC_TYPES }, { key: "status", label: "Status", options: ["New", "Reviewing", "Flagged", "Cleared", "Archived"] }]}
            addLabel="New Contract" emptyTitle="No contracts" searchPlaceholder="Search contracts…" />
        </TabsContent>
        <TabsContent value="vendors">
          <EntityLedger entityName="Vendors" fields={vendorFields} columns={vendorColumns}
            searchKeys={["name", "vendor_id", "normalized_name", "municipality"]}
            filterDefs={[{ key: "review_status", label: "Review", options: ["Unreviewed", "Reviewing", "Reviewed", "NeedsFollowup"] }]}
            addLabel="New Vendor" emptyTitle="No vendors" searchPlaceholder="Search vendors…" />
        </TabsContent>
        <TabsContent value="flags">
          <EntityLedger entityName="AnomalyFlags" fields={flagFields} columns={flagColumns}
            searchKeys={["flag_id", "contract_id", "rationale"]}
            filterDefs={[{ key: "flag_type", label: "Type", options: FLAG_TYPES }, { key: "severity", label: "Severity", options: ["Low", "Medium", "High", "Critical"] }]}
            addLabel="New Flag" emptyTitle="No anomaly flags"
            emptyDescription="Anomaly detection requires contract/vendor-level enrichment not yet in the canonical federation export — data pending richer MoneySweep-PR intake."
            searchPlaceholder="Search flags…" />
        </TabsContent>
      </Tabs>
    </div>
  );
}