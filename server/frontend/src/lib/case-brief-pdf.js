import { jsPDF } from "jspdf";
import { getCaseGateProgress, CASE_STAGES } from "@/lib/case-gate-progress";
import { getBriefTemplate, DEFAULT_TEMPLATE_ID } from "@/lib/case-brief-templates";

// Leadership brief for a single case, rendered from a chosen template style.
// Pulls: case summary, validation progress, current confidence, and (for
// detailed templates) recent related AnomalyFlags.
// Neutral analytical language only — anomalies presented as review items.

// Recent anomalies related to a case via its linked sources' source_id.
function relatedAnomalies(caseRow, allSources, allAnomalies) {
  const sourceIds = (allSources || [])
    .filter((s) => s.linked_case_id === caseRow.case_id)
    .map((s) => s.source_id);
  if (!sourceIds.length) return [];
  return (allAnomalies || [])
    .filter((a) => sourceIds.includes(a.source_id))
    .slice(0, 8);
}

export function generateCaseBriefPdf(caseRow, sources, anomalies, templateId = DEFAULT_TEMPLATE_ID) {
  const tpl = getBriefTemplate(templateId);
  const progress = getCaseGateProgress(caseRow, sources);
  const doc = new jsPDF();
  const M = 18;
  const barW = 210 - M * 2;
  const [aR, aG, aB] = tpl.accent;
  let y = 20;

  // Header
  doc.setFontSize(9);
  doc.setTextColor(aR, aG, aB);
  doc.text(tpl.headerTitle, M, y);
  doc.setTextColor(120);
  doc.text(new Date().toLocaleString(), 210 - M, y, { align: "right" });
  y += 8;
  doc.setDrawColor(aR, aG, aB);
  doc.line(M, y, 210 - M, y);
  y += 10;

  // Title block
  doc.setFontSize(tpl.titleSize);
  doc.setTextColor(20);
  doc.text(caseRow.title || "Untitled Case", M, y);
  y += 7;
  doc.setFontSize(10);
  doc.setTextColor(110);
  doc.text(
    `${caseRow.case_code || caseRow.case_id || "—"}  ·  ${caseRow.case_type || "—"}  ·  ${caseRow.municipality || "—"}`,
    M, y
  );
  y += 6;
  doc.text(`Status: ${caseRow.status || "—"}    Sensitivity: ${caseRow.sensitivity || "—"}`, M, y);
  y += 12;

  // Confidence
  if (tpl.sections.confidence) {
    doc.setFontSize(11);
    doc.setTextColor(20);
    doc.text("Current Confidence", M, y);
    doc.setTextColor(110);
    doc.text(`${caseRow.confidence || "Low"}`, M + 60, y);
    y += 10;
  }

  // Validation progress label + bar + stage markers
  if (tpl.sections.validation) {
    doc.setFontSize(11);
    doc.setTextColor(20);
    doc.text("Validation Progress", M, y);
    doc.setTextColor(110);
    doc.text(`${progress.blocked ? "Contradicted — review" : progress.label} (${progress.percent}%)`, M + 60, y);
    y += 5;

    const fill = progress.blocked ? 100 : progress.percent;
    doc.setFillColor(230);
    doc.roundedRect(M, y, barW, 4, 2, 2, "F");
    if (progress.blocked) doc.setFillColor(245, 158, 11);
    else if (progress.percent >= 100) doc.setFillColor(16, 185, 129);
    else doc.setFillColor(aR, aG, aB);
    doc.roundedRect(M, y, (barW * fill) / 100, 4, 2, 2, "F");
    y += 9;

    doc.setFontSize(8);
    const stageW = barW / CASE_STAGES.length;
    CASE_STAGES.forEach((s, i) => {
      doc.setTextColor(i <= progress.stageIndex ? 60 : 170);
      doc.text(s.label, M + stageW * i + stageW / 2, y, { align: "center" });
    });
    y += 6;
    doc.setFontSize(9);
    doc.setTextColor(110);
    doc.text(`Evidence: best tier ${progress.bestTier || "—"} · ${progress.verifiedCount}/${progress.sourceCount} sources verified`, M, y);
    y += 12;
  }

  // Public summary
  if (tpl.sections.summary) {
    doc.setFontSize(11);
    doc.setTextColor(20);
    doc.text("Summary", M, y);
    y += 6;
    doc.setFontSize(10);
    doc.setTextColor(80);
    const summary = caseRow.summary_public || "No public summary recorded.";
    doc.splitTextToSize(summary, barW).slice(0, tpl.summaryMaxLines).forEach((line) => {
      if (y > 270) { doc.addPage(); y = 20; }
      doc.text(line, M, y);
      y += 5;
    });
    y += 8;
  }

  // Recent related anomaly flags
  if (tpl.sections.anomalies) {
    const anoms = relatedAnomalies(caseRow, sources, anomalies);
    doc.setFontSize(11);
    doc.setTextColor(20);
    if (y > 250) { doc.addPage(); y = 20; }
    doc.text("Recent Related Anomaly Flags (review items)", M, y);
    y += 6;
    doc.setFontSize(9);
    if (!anoms.length) {
      doc.setTextColor(120);
      doc.text("No related anomaly flags linked through this case's sources.", M, y);
      y += 5;
    } else {
      anoms.forEach((a) => {
        if (y > 268) { doc.addPage(); y = 20; }
        doc.setTextColor(40);
        doc.text(`• ${a.flag_type} — Severity ${a.severity} · Confidence ${a.confidence} · ${a.review_status}`, M, y);
        y += 5;
        if (a.rationale) {
          doc.setTextColor(110);
          doc.splitTextToSize(a.rationale, barW - 6).slice(0, 2).forEach((line) => {
            if (y > 272) { doc.addPage(); y = 20; }
            doc.text(line, M + 4, y);
            y += 4.5;
          });
        }
        y += 2;
      });
    }
  }

  // Footer caveat
  doc.setFontSize(8);
  doc.setTextColor(150);
  doc.text(
    "Analytical brief. Items represent leads/observations under review, not conclusions. Source lineage preserved in INTSYS-PR.",
    M, 285
  );

  doc.save(`case-brief-${tpl.id}-${caseRow.case_code || caseRow.case_id || "record"}.pdf`);
}