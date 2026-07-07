// Leadership case-brief PDF template library.
// Each template controls layout density, accent color, and which sections are
// rendered. Neutral analytical language is preserved across all styles.

export const BRIEF_TEMPLATES = {
  executive: {
    id: "executive",
    label: "Executive Summary",
    description: "One-page leadership snapshot: header, confidence, validation bar, summary.",
    accent: [37, 99, 235], // blue-600
    headerTitle: "INTSYS-PR Federation — Executive Case Brief",
    titleSize: 18,
    sections: { confidence: true, validation: true, summary: true, anomalies: false },
    summaryMaxLines: 8,
  },
  detailed: {
    id: "detailed",
    label: "Detailed Analytical",
    description: "Full brief with validation stages, evidence tiers, and related anomaly flags.",
    accent: [124, 58, 237], // violet-600
    headerTitle: "INTSYS-PR Federation — Detailed Case Brief",
    titleSize: 16,
    sections: { confidence: true, validation: true, summary: true, anomalies: true },
    summaryMaxLines: 999,
  },
  minimal: {
    id: "minimal",
    label: "Minimal / Print",
    description: "Compact monochrome layout: title, status line, and summary only.",
    accent: [71, 85, 105], // slate-600
    headerTitle: "INTSYS-PR — Case Brief",
    titleSize: 15,
    sections: { confidence: true, validation: false, summary: true, anomalies: false },
    summaryMaxLines: 999,
  },
};

export const BRIEF_TEMPLATE_LIST = Object.values(BRIEF_TEMPLATES);

export const DEFAULT_TEMPLATE_ID = "detailed";

export function getBriefTemplate(id) {
  return BRIEF_TEMPLATES[id] || BRIEF_TEMPLATES[DEFAULT_TEMPLATE_ID];
}