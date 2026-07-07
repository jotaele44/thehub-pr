import { HUB_REPO } from "@/lib/federation";

const COLS = [
  "crossover_id", "source_module", "source_record_id", "source_label",
  "target_module", "target_record_id", "target_label", "related_modules",
  "related_record_ids", "correlation_type", "status", "verified", "confidence_score", "confidence_band",
  "evidence_tier", "rationale", "source_ids", "contradiction_notes",
  "matching_criteria", "created_from", "municipality", "agency", "vendor", "date", "source_repo",
];

const esc = (v) => {
  if (v === null || v === undefined) return "";
  const s = Array.isArray(v) ? v.join("; ") : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

export function exportCrossoversCsv(rows) {
  const header = COLS.join(",");
  const body = rows.map((r) =>
    COLS.map((c) => esc(c === "source_repo" ? HUB_REPO : r[c])).join(",")
  ).join("\n");
  const blob = new Blob([`${header}\n${body}`], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `federation-crossovers-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}