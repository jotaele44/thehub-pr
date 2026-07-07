// Output styles for the case-brief PDF generator.

export const BRIEF_TEMPLATES = {
  standard: {
    id: "standard",
    label: "Standard Brief",
    description: "Full case brief: summary, metadata, linked sources with evidence tiers, and anomaly flags.",
    sections: ["summary", "metadata", "sources", "anomalies"],
  },
  executive: {
    id: "executive",
    label: "Executive Summary",
    description: "One-page leadership view: public summary and key metadata only.",
    sections: ["summary", "metadata"],
  },
  evidence: {
    id: "evidence",
    label: "Evidence Annex",
    description: "Source-focused annex: every linked source with tier, reliability, and verification status.",
    sections: ["metadata", "sources"],
  },
};

export const BRIEF_TEMPLATE_LIST = Object.values(BRIEF_TEMPLATES);
export const DEFAULT_TEMPLATE_ID = "standard";
