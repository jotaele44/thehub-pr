import { toCsv, downloadFile } from "@/lib/export";

const COLUMNS = [
  "crossover_id",
  "source_module",
  "source_label",
  "source_record_id",
  "target_module",
  "target_label",
  "target_record_id",
  "status",
  "correlation_type",
  "confidence_band",
  "confidence_score",
  "evidence_tier",
  "municipality",
  "agency",
  "vendor",
  "date",
  "rationale",
  "matching_criteria",
  "source_ids",
  "created_from",
  "contradiction_notes",
];

// Export the (filtered) crossover set as a provenance-preserving CSV.
export function exportCrossoversCsv(crossovers = []) {
  const rows = crossovers.map((c) => ({
    ...c,
    matching_criteria: (c.matching_criteria || []).join("; "),
    source_ids: (c.source_ids || []).join("; "),
  }));
  const fileName = `federation-crossovers-${new Date().toISOString().slice(0, 10)}.csv`;
  downloadFile(toCsv(rows, COLUMNS), fileName, "text/csv;charset=utf-8");
  return { fileName, count: rows.length };
}
