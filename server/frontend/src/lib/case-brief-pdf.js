import { jsPDF } from "jspdf";
import { BRIEF_TEMPLATES, DEFAULT_TEMPLATE_ID } from "@/lib/case-brief-templates";

const unwrap = (row) => (row && row.data ? { ...row.data, id: row.id ?? row.data.id } : row);

const matchesCase = (record, caseRow) => {
  const ids = new Set([caseRow?.case_id, caseRow?.case_code, caseRow?.id].filter(Boolean).map(String));
  const ref = record?.case_id || record?.linked_case_id || record?.related_case_id;
  return ref && ids.has(String(ref));
};

// Generate and download a case-brief PDF for the given template id.
export function generateCaseBriefPdf(caseRow, sources = [], anomalies = [], templateId = DEFAULT_TEMPLATE_ID) {
  const template = BRIEF_TEMPLATES[templateId] || BRIEF_TEMPLATES[DEFAULT_TEMPLATE_ID];
  const c = unwrap(caseRow) || {};
  const linkedSources = sources.map(unwrap).filter((s) => matchesCase(s, c));
  const linkedAnomalies = anomalies.map(unwrap).filter((a) => matchesCase(a, c));

  const doc = new jsPDF({ unit: "pt", format: "letter" });
  const margin = 48;
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const maxWidth = pageWidth - margin * 2;
  let y = margin;

  const ensureRoom = (needed = 16) => {
    if (y + needed > pageHeight - margin) {
      doc.addPage();
      y = margin;
    }
  };

  const writeLines = (text, size = 10, style = "normal", gap = 4) => {
    doc.setFont("helvetica", style);
    doc.setFontSize(size);
    const lines = doc.splitTextToSize(String(text ?? "—"), maxWidth);
    for (const line of lines) {
      ensureRoom(size + gap);
      doc.text(line, margin, y);
      y += size + gap;
    }
  };

  const heading = (text) => {
    y += 8;
    writeLines(text, 12, "bold", 6);
  };

  // Header
  writeLines(`Case Brief — ${c.case_code || c.case_id || "Untitled Case"}`, 16, "bold", 8);
  writeLines(`${template.label} · Generated ${new Date().toLocaleString()} · Source repo: thehub-pr`, 8, "normal", 10);
  writeLines(c.title || "", 12, "bold", 8);

  if (template.sections.includes("summary")) {
    heading("Public Summary");
    writeLines(c.summary_public || c.summary || "No public summary recorded.");
  }

  if (template.sections.includes("metadata")) {
    heading("Case Metadata");
    const rows = [
      ["Case ID", c.case_id],
      ["Case Code", c.case_code],
      ["Program", c.program_id],
      ["Type", c.case_type],
      ["Status", c.status],
      ["Event Date", c.event_date],
      ["Date Precision", c.date_precision],
      ["Municipality", c.municipality],
      ["Region", c.region],
      ["Coordinates", (c.latitude || c.longitude) ? `${c.latitude ?? "—"}, ${c.longitude ?? "—"}` : null],
      ["Confidence", c.confidence],
      ["Sensitivity", c.sensitivity],
    ];
    for (const [label, value] of rows) {
      if (value === undefined || value === null || value === "") continue;
      writeLines(`${label}: ${value}`, 10, "normal", 4);
    }
  }

  if (template.sections.includes("sources")) {
    heading(`Linked Sources (${linkedSources.length})`);
    if (!linkedSources.length) {
      writeLines("No sources linked to this case.");
    } else {
      linkedSources.forEach((s, i) => {
        writeLines(`${i + 1}. ${s.title || s.source_id || "Untitled source"}`, 10, "bold", 4);
        const meta = [
          s.evidence_tier && `Tier ${s.evidence_tier}`,
          s.reliability && `Reliability: ${s.reliability}`,
          s.verification_status && `Verification: ${s.verification_status}`,
          s.sensitivity && `Sensitivity: ${s.sensitivity}`,
        ].filter(Boolean).join(" · ");
        if (meta) writeLines(meta, 9, "normal", 4);
        if (s.url) writeLines(s.url, 8, "italic", 6);
      });
    }
  }

  if (template.sections.includes("anomalies")) {
    heading(`Anomaly Flags (${linkedAnomalies.length})`);
    if (!linkedAnomalies.length) {
      writeLines("No anomaly flags linked to this case.");
    } else {
      linkedAnomalies.forEach((a, i) => {
        writeLines(`${i + 1}. ${a.summary || a.anomaly_id || "Anomaly"}`, 10, "bold", 4);
        const meta = [
          a.severity && `Severity: ${a.severity}`,
          a.confidence && `Confidence: ${a.confidence}`,
          a.review_status && `Review: ${a.review_status}`,
        ].filter(Boolean).join(" · ");
        if (meta) writeLines(meta, 9, "normal", 6);
      });
    }
  }

  y += 12;
  writeLines("Provenance preserved · IDs, evidence tiers, and review status retained. Correlation ≠ causation.", 8, "italic", 4);

  const fileName = `case-brief-${(c.case_code || c.case_id || "case").toString().toLowerCase().replace(/[^a-z0-9-]+/g, "-")}-${template.id}.pdf`;
  doc.save(fileName);
  return { fileName };
}
