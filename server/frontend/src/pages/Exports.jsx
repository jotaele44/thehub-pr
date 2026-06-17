import React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { federation } from "@/api/federationClient";
import { Download } from "lucide-react";
import PageHeader from "@/components/shared/PageHeader";
import StatCard from "@/components/shared/StatCard";
import LedgerExportRow from "@/components/exports/LedgerExportRow";
import ExportHistory from "@/components/exports/ExportHistory";
import { EXPORT_LEDGERS } from "@/lib/export-config";
import { HUB_REPO } from "@/lib/federation";
import { toast } from "sonner";

const highestSensitivity = (records) => {
  const rank = { Public: 0, Internal: 1, Restricted: 2 };
  let best = null, bestRank = -1;
  for (const rec of records) {
    const s = (rec.data || rec).sensitivity;
    if (s && rank[s] > bestRank) { best = s; bestRank = rank[s]; }
  }
  return best || "Public";
};

const tiersIn = (records) => {
  const set = new Set();
  for (const rec of records) {
    const t = (rec.data || rec).evidence_tier;
    if (t) set.add(t);
  }
  return Array.from(set);
};

export default function ExportsPage() {
  const qc = useQueryClient();

  const { data: exports = [] } = useQuery({
    queryKey: ["Exports"],
    queryFn: () => federation.entities.Exports.list("-generated_at", 100),
    initialData: [],
  });

  const recordExport = async ({ ledger, format, fileName, count, records }) => {
    const me = await federation.auth.me().catch(() => null);
    const nowIso = new Date().toISOString();
    const id = `exp-${ledger.entity.toLowerCase()}-${Date.now()}`;
    await federation.entities.Exports.create({
      export_id: id,
      module: ledger.module,
      ledger: ledger.entity,
      export_format: format,
      record_count: count,
      filters_applied: "Full ledger (no filters)",
      evidence_tiers_included: tiersIn(records),
      sensitivity_max: highestSensitivity(records),
      provenance_preserved: true,
      status: "Downloaded",
      file_name: fileName,
      source_repo: HUB_REPO,
      legacy_repo: HUB_REPO,
      generated_by: me?.email || "unknown",
      generated_at: nowIso,
    });
    await federation.entities.AuditLog.create({
      log_id: `log-${Date.now()}`,
      module: ledger.module,
      action: "Export",
      entity_name: ledger.entity,
      record_id: id,
      summary: `Exported ${count} ${ledger.label} record(s) as ${format}.`,
      actor: me?.email || "unknown",
      occurred_at: nowIso,
      source_repo: HUB_REPO,
    });
    qc.invalidateQueries({ queryKey: ["Exports"] });
    toast.success(`${ledger.label} exported (${count} records)`);
  };

  const realExports = exports.map((e) => e.data || e).filter((e) => !e.test_record);
  const totalExports = realExports.length;
  const geoLedgers = EXPORT_LEDGERS.filter((l) => l.geo).length;

  return (
    <div className="p-5 lg:p-8 max-w-[100rem] mx-auto">
      <PageHeader
        title="Exports"
        description="Provenance-preserving CSV and GeoJSON export across federation ledgers. Every export keeps IDs, source repo, module, evidence tier, confidence, and review status, and is logged for audit."
        icon={Download}
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <StatCard label="Exportable Ledgers" value={EXPORT_LEDGERS.length} />
        <StatCard label="Geospatial (GeoJSON)" value={geoLedgers} />
        <StatCard label="Exports Logged" value={totalExports} />
        <StatCard label="Source Repo" value={HUB_REPO} />
      </div>

      <div className="space-y-5">
        <section>
          <h2 className="text-sm font-semibold text-foreground mb-3">Ledger Exports</h2>
          <div className="grid gap-3">
            {EXPORT_LEDGERS.map((l) => (
              <LedgerExportRow key={l.entity} ledger={l} onExport={recordExport} />
            ))}
          </div>
        </section>

        <section>
          <h2 className="text-sm font-semibold text-foreground mb-3">Export History</h2>
          <ExportHistory records={realExports} />
        </section>
      </div>
    </div>
  );
}