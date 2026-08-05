// Crossover derivation for the Federation Crossover Workspace.
// Explicit, review-managed CrossoverLinks rows are the source of truth; each
// is normalized into the display shape consumed by CrossoverCard / matrix /
// pair panels. ILAP candidates / POIs come from GraphNodes with controlled
// node_type values. Inferred (candidate) matching is intentionally out of
// scope in local mode — uncertainty stays explicit.

const ILAP_TYPES = new Set([
  "ILAP_CANDIDATE",
  "POI",
  "LAND_DEVELOPMENT_SITE",
  "INFRASTRUCTURE_ADJACENT_POI",
]);

const unwrap = (row) => (row && row.data ? { ...row.data, id: row.id ?? row.data.id } : row);

const bandFromScore = (score) => {
  if (score === undefined || score === null || Number.isNaN(Number(score))) return "Low";
  const s = Number(score);
  if (s >= 70) return "High";
  if (s >= 40) return "Medium";
  return "Low";
};

export function computeCrossovers({
  unifiedSources = [],
  crossoverLinks = [],
  graphNodes = [],
  evidenceStandards = [],
} = {}) {
  const sources = unifiedSources.map(unwrap);
  const links = crossoverLinks.map(unwrap);
  const nodes = graphNodes.map(unwrap);
  const standards = evidenceStandards.map(unwrap);

  const sourceById = new Map();
  for (const s of sources) {
    const key = s.source_id || s.id;
    if (key) sourceById.set(String(key), s);
  }

  const tierMeaning = new Map();
  for (const es of standards) {
    if (es.tier) tierMeaning.set(es.tier, { label: es.label || es.name || "", definition: es.definition || es.description || "" });
  }

  const crossovers = links.map((l, i) => {
    const sourceIds = Array.isArray(l.source_ids)
      ? l.source_ids
      : (l.source_ids ? String(l.source_ids).split(",").map((s) => s.trim()).filter(Boolean) : []);

    const resolvedSources = sourceIds.map((id) => {
      const s = sourceById.get(String(id));
      return s
        ? { id, title: s.title || s.name || String(id), url: s.url || s.source_url || null, tier: s.evidence_tier || null }
        : { id, title: null, url: null, tier: null };
    });

    const score = Number(l.confidence_score ?? l.score ?? 0) || 0;

    return {
      crossover_id: l.crossover_id || l.link_id || l.id || `cx-${i}`,
      source_module: l.source_module || "Hub",
      target_module: l.target_module || "Hub",
      source_label: l.source_label || l.source_title || l.source_record_id || "—",
      target_label: l.target_label || l.target_title || l.target_record_id || "—",
      source_record_id: l.source_record_id || null,
      target_record_id: l.target_record_id || null,
      status: l.status || "Candidate",
      correlation_type: l.correlation_type || l.crossover_type || "Other",
      confidence_score: score,
      confidence_band: l.confidence_band || bandFromScore(score),
      evidence_tier: l.evidence_tier || null,
      tier_meaning: l.evidence_tier ? tierMeaning.get(l.evidence_tier) || null : null,
      rationale: l.rationale || l.notes || "",
      matching_criteria: Array.isArray(l.matching_criteria)
        ? l.matching_criteria
        : (l.matching_criteria ? [String(l.matching_criteria)] : []),
      created_from: l.created_from || "CrossoverLinks ledger",
      contradiction_notes: l.contradiction_notes || null,
      related_modules: Array.isArray(l.related_modules) ? l.related_modules : undefined,
      source_ids: sourceIds,
      resolved_sources: resolvedSources,
      municipality: l.municipality || null,
      agency: l.agency || null,
      vendor: l.vendor || l.vendor_name || null,
      date: l.date || l.event_date || l.created_date || null,
    };
  });

  const ilapNodes = nodes.filter((n) => ILAP_TYPES.has(n.node_type));

  return { crossovers, ilapNodes };
}
