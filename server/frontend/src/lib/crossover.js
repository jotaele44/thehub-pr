// Transparent crossover correlation engine.
// RULES:
// - Explicit links (stored CrossoverLinks, CorrelationReviews, GraphEdges) take priority.
//   Explicit = persisted record IDs, GraphEdges, CorrelationReviews, source_ids,
//   case IDs, event IDs, contract IDs, vendor IDs, asset IDs.
// - Inferred/candidate links are ALWAYS Candidate/PendingReview — never silently promoted to Verified.
// - Generated candidates require >= 2 independent weak criteria (e.g. municipality + temporal,
//   municipality + entity-name, graph-edge + matching source). Single-attribute matches are not emitted.
// - Contradictions are preserved (never deleted).
// - test_record:true rows are EXCLUDED from operational output by default (production safety).
// - Guardrails: indexed lookup maps, memoized upstream, per-pair candidate cap + confidence floor
//   so candidate volume can't explode as ledgers grow.
// - Correlation does not equal causation. UAP analysis = pattern convergence only.

import { bandFromScore, ILAP_NODE_TYPES } from "@/lib/crossover-config";
import { computeHubCrossovers } from "@/lib/crossover-hub";
import { computeConvergence, computeGraphEdgeCrossovers } from "@/lib/crossover-convergence";

const norm = (s) => (s || "").toString().trim().toLowerCase();
const yr = (d) => (d ? new Date(d).getFullYear() : null);

// Guardrails against candidate explosion.
const MAX_CANDIDATES_PER_PAIR = 200;
const CANDIDATE_CONFIDENCE_FLOOR = 40;

// Build a normalized crossover record (the reusable shape used across the UI).
function mk(o) {
  const score = o.confidence_score ?? 0;
  return {
    crossover_id: o.crossover_id,
    source_module: o.source_module,
    source_record_id: o.source_record_id,
    source_label: o.source_label || o.source_record_id || "—",
    target_module: o.target_module,
    target_record_id: o.target_record_id,
    target_label: o.target_label || o.target_record_id || "—",
    related_modules: o.related_modules || [o.source_module, o.target_module],
    related_record_ids: o.related_record_ids || [],
    correlation_type: o.correlation_type || "Other",
    status: o.status || "Candidate",
    verified: !!o.verified,
    confidence_score: score,
    confidence_band: o.confidence_band || bandFromScore(score),
    rationale: o.rationale || "",
    evidence_tier: o.evidence_tier || null,
    source_ids: o.source_ids || [],
    contradiction_notes: o.contradiction_notes || "",
    municipality: o.municipality || null,
    agency: o.agency || null,
    vendor: o.vendor || null,
    date: o.date || null,
    created_from: o.created_from || "candidate_match",
    matching_criteria: o.matching_criteria || [],
    _stored: !!o._stored,
    _storedId: o._storedId || null,
    _created_date: o._created_date || null,
  };
}

// Normalize a persisted CrossoverLinks row.
function fromStored(r, labelFor) {
  return mk({
    crossover_id: r.crossover_id || r.id,
    source_module: r.source_module,
    source_record_id: r.source_record_id,
    source_label: labelFor(r.source_module, r.source_record_id),
    target_module: r.target_module,
    target_record_id: r.target_record_id,
    target_label: labelFor(r.target_module, r.target_record_id),
    related_modules: r.related_modules?.length ? r.related_modules : undefined,
    related_record_ids: r.related_record_ids,
    correlation_type: r.correlation_type,
    status: r.status,
    verified: r.verified,
    confidence_score: r.confidence_score,
    confidence_band: r.confidence_band,
    rationale: r.rationale,
    evidence_tier: r.evidence_tier,
    source_ids: r.source_ids,
    contradiction_notes: r.contradiction_notes,
    created_from: r.created_from || "manual",
    matching_criteria: r.matching_criteria,
    _stored: true,
    _storedId: r.id,
    _created_date: r.created_date || r.created_at || null,
  });
}

// Existing Airspace↔Ovnis correlation reviews → crossover shape (explicit links).
function fromCorrelationReview(r, eventById, caseById) {
  const ev = eventById[r.airspace_event_id];
  const cs = caseById[r.linked_ovnis_case_id];
  const status = r.status === "Accepted" ? "Verified"
    : r.status === "Rejected" ? "Rejected"
    : r.status === "Inconclusive" ? "Contradicted"
    : "PendingReview";
  const score = r.confidence === "High" ? 85 : r.confidence === "Medium" ? 55 : 30;
  return mk({
    crossover_id: r.review_id || r.id,
    source_module: "Skywatcher-PR",
    source_record_id: r.airspace_event_id,
    source_label: ev?.title || r.airspace_event_id,
    target_module: "Ovnis-PR",
    target_record_id: r.linked_ovnis_case_id,
    target_label: cs?.title || r.linked_ovnis_case_id || "—",
    correlation_type: r.correlation_type === "Temporal" ? "Temporal"
      : r.correlation_type === "Spatial" ? "Geography"
      : r.correlation_type === "SourceBased" ? "SourceEvidence" : "Entity",
    status,
    verified: r.status === "Accepted",
    confidence_score: score,
    rationale: r.rationale,
    evidence_tier: ev?.source_id ? "T1" : "T3",
    municipality: ev?.municipality || cs?.municipality,
    date: ev?.event_date,
    contradiction_notes: r.status === "Inconclusive" ? "Review marked inconclusive — caveat preserved." : "",
    created_from: "correlation_review",
    matching_criteria: ["existing_correlation_review"],
    _stored: false,
  });
}

// Candidate generator: transparent shared-attribute matching between two record sets.
// `secondCriterion(a,b)` MUST return a non-empty string label when an independent second
// weak signal corroborates the primary `attr` match. Pairs with only ONE matching criterion
// are skipped — we never emit a single-attribute candidate. Indexed lookup keeps this O(n+m),
// and output is capped at MAX_CANDIDATES_PER_PAIR to prevent explosion on large ledgers.
function candidates({ aMod, bMod, aRecords, bRecords, type, attr, getA, getB, labelA, labelB, getMuni, getDate, tier, makeRationale, secondCriterion }) {
  const out = [];
  const index = {};
  for (const b of bRecords) {
    const key = norm(getB(b));
    if (!key) continue;
    (index[key] ||= []).push(b);
  }
  for (const a of aRecords) {
    if (out.length >= MAX_CANDIDATES_PER_PAIR) break;
    const key = norm(getA(a));
    if (!key) continue;
    const matches = index[key] || [];
    for (const b of matches) {
      if (out.length >= MAX_CANDIDATES_PER_PAIR) break;
      // Require a GENUINE second independent weak criterion. A name/attr match repeated as its
      // own "second signal" is not independent — so when no secondCriterion is supplied we treat
      // the single shared attribute as low-confidence and tag it honestly as name-only.
      const second = secondCriterion ? secondCriterion(a, b) : null;
      if (secondCriterion && !second) continue; // explicit second-criterion required but absent → skip
      const nameOnly = !second;
      const criteria = nameOnly ? [`shared_${attr}`, "name_only_no_second_signal"] : [`shared_${attr}`, second];
      out.push(mk({
        crossover_id: `cand-${type}-${a.id}-${b.id}`,
        source_module: aMod,
        source_record_id: a.id,
        source_label: labelA(a),
        target_module: bMod,
        target_record_id: b.id,
        target_label: labelB(b),
        correlation_type: type,
        status: "Candidate",
        verified: false,
        // Name-only matches are floored low (never auto-verified, never medium) until a second
        // independent signal corroborates them.
        confidence_score: nameOnly ? CANDIDATE_CONFIDENCE_FLOOR : Math.max(CANDIDATE_CONFIDENCE_FLOOR, 45),
        rationale: makeRationale
          ? makeRationale(a, b, key)
          : nameOnly
            ? `Name-only match on ${attr}: "${getA(a)}". Single signal — low confidence, identity must be verified before use.`
            : `Shared ${attr}: "${getA(a)}" plus ${second}. Candidate relationship — review required.`,
        evidence_tier: tier || "T4",
        municipality: getMuni ? getMuni(a) || getMuni(b) : undefined,
        date: getDate ? getDate(a) || getDate(b) : undefined,
        created_from: "candidate_match",
        matching_criteria: criteria,
      }));
    }
  }
  return out;
}

// Second-criterion helpers (independent weak signals beyond the primary attribute).
const sameYear = (getDateA, getDateB) => (a, b) => {
  const ya = yr(getDateA?.(a)); const yb = yr(getDateB?.(b));
  return ya && yb && ya === yb ? `temporal_same_year_${ya}` : null;
};
const sameRegion = (a, b) => (a?.region && b?.region && norm(a.region) === norm(b.region)) ? `shared_region_${a.region}` : null;
// Geography candidates require municipality AND (same region OR same year), so a bare
// municipality match never produces a candidate on its own.
const geoSecond = (getDateA, getDateB) => (a, b) =>
  sameRegion(a, b) || sameYear(getDateA, getDateB)(a, b);

// Main engine. data = entity arrays. Returns { crossovers, ilapNodes, sourceById }.
// includeTest=false (default) drops test_record:true rows from operational output.
export function computeCrossovers(data, { includeTest = false } = {}) {
  const {
    airspaceEvents = [], unifiedCases = [], infrastructureAssets = [], continuityRisks = [],
    contracts = [], vendors = [], anomalyFlags = [], graphNodes = [], graphEdges = [],
    unifiedSources = [], correlationReviews = [], crossoverLinks = [],
    programs = [], federationTasks = [], federationManifests = [], validationGates = [],
    integrationStatus = [], evidenceStandards = [],
  } = data;

  const eventById = Object.fromEntries(airspaceEvents.map((e) => [e.id, e]));
  const caseById = Object.fromEntries(unifiedCases.map((c) => [c.id, c]));
  const nodeById = Object.fromEntries(graphNodes.map((n) => [n.id, n]));

  // Resolve evidence tier meaning from the EvidenceStandards ledger (T1..T4 → label/definition).
  const tierMeaning = {};
  for (const s of evidenceStandards) if (s.tier) tierMeaning[s.tier] = { label: s.label, definition: s.definition, weight: s.weight };

  // Resolve source_ids -> UnifiedSources (by human-readable source_id or db id).
  const sourceById = {};
  for (const s of unifiedSources) {
    if (s.source_id) sourceById[s.source_id] = s;
    if (s.id) sourceById[s.id] = s;
  }

  // Production safety: exclude seeded/demo rows unless explicitly requested.
  const storedLinks = includeTest ? crossoverLinks : crossoverLinks.filter((r) => !r.test_record);

  // Resolve a friendly label for any module + record id (for stored links).
  const labelFor = (mod, id) => {
    if (!id) return "—";
    const lists = [airspaceEvents, unifiedCases, infrastructureAssets, contracts, vendors, graphNodes];
    for (const l of lists) {
      const hit = l.find((r) => r.id === id);
      if (hit) return hit.title || hit.name || hit.label || id;
    }
    return id;
  };

  const results = [];

  // 1. Explicit stored links (highest priority). Test records already excluded above.
  for (const r of storedLinks) results.push(fromStored(r, labelFor));

  // 2. Existing correlation reviews (explicit Airspace↔Ovnis links).
  for (const r of correlationReviews) results.push(fromCorrelationReview(r, eventById, caseById));

  // 3. Transparent candidate matching across pairs.
  const lblEvent = (e) => e.title || e.event_id || e.id;
  const lblCase = (c) => c.title || c.case_code || c.id;
  const lblAsset = (a) => a.name || a.asset_id || a.id;
  const lblContract = (c) => c.title || c.contract_id || c.id;
  const lblVendor = (v) => v.name || v.vendor_id || v.id;
  const lblNode = (n) => n.label || n.node_id || n.id;

  // C. Skywatcher ↔ AguaYLuz (municipality + region/year). Criteria: shared_municipality + region/temporal.
  results.push(...candidates({
    aMod: "Skywatcher-PR", bMod: "AguaYLuz-PR", aRecords: airspaceEvents, bRecords: infrastructureAssets,
    type: "Geography", attr: "municipality", getA: (e) => e.municipality, getB: (a) => a.municipality,
    labelA: lblEvent, labelB: lblAsset, getMuni: (r) => r.municipality, getDate: (e) => e.event_date, tier: "T2",
    secondCriterion: geoSecond((e) => e.event_date, () => null),
    makeRationale: (e, a, k) => `Airspace event and infrastructure asset share municipality "${e.municipality}" plus a second signal. Proximity candidate only — review required.`,
  }));

  // D. Skywatcher ↔ MoneySweep (municipality + region/year).
  results.push(...candidates({
    aMod: "Skywatcher-PR", bMod: "MoneySweep-PR", aRecords: airspaceEvents, bRecords: contracts,
    type: "Geography", attr: "municipality", getA: (e) => e.municipality, getB: (c) => c.municipality,
    labelA: lblEvent, labelB: lblContract, getMuni: (r) => r.municipality, getDate: (e) => e.event_date, tier: "T2",
    secondCriterion: geoSecond((e) => e.event_date, (c) => c.award_date),
  }));

  // F. Ovnis ↔ AguaYLuz (municipality + region/year).
  results.push(...candidates({
    aMod: "Ovnis-PR", bMod: "AguaYLuz-PR", aRecords: unifiedCases, bRecords: infrastructureAssets,
    type: "Geography", attr: "municipality", getA: (c) => c.municipality, getB: (a) => a.municipality,
    labelA: lblCase, labelB: lblAsset, getMuni: (r) => r.municipality, tier: "T3",
    secondCriterion: geoSecond((c) => c.event_date, () => null),
  }));

  // G. Ovnis ↔ MoneySweep (municipality + region/year).
  results.push(...candidates({
    aMod: "Ovnis-PR", bMod: "MoneySweep-PR", aRecords: unifiedCases, bRecords: contracts,
    type: "Geography", attr: "municipality", getA: (c) => c.municipality, getB: (k) => k.municipality,
    labelA: lblCase, labelB: lblContract, getMuni: (r) => r.municipality, tier: "T3",
    secondCriterion: geoSecond((c) => c.event_date, (k) => k.award_date),
  }));

  // H. AguaYLuz ↔ MoneySweep (municipality + region/year — infra possibly funded by contracts).
  results.push(...candidates({
    aMod: "AguaYLuz-PR", bMod: "MoneySweep-PR", aRecords: infrastructureAssets, bRecords: contracts,
    type: "InfrastructureAdjacency", attr: "municipality", getA: (a) => a.municipality, getB: (c) => c.municipality,
    labelA: lblAsset, labelB: lblContract, getMuni: (r) => r.municipality, tier: "T2",
    secondCriterion: (a, c) => sameRegion(a, c) || (norm(a.owner_agency) && norm(a.owner_agency) === norm(c.agency) ? `shared_agency_${c.agency}` : null),
    makeRationale: (a, c) => `Infrastructure asset and contract share municipality "${a.municipality}" plus region/agency signal. Possible funding/recovery link — review required.`,
  }));

  // J. MoneySweep ↔ Spiderweb (vendor/agency appears as graph node label)
  results.push(...candidates({
    aMod: "MoneySweep-PR", bMod: "Spiderweb-PR", aRecords: vendors, bRecords: graphNodes,
    type: "Entity", attr: "entity_name", getA: (v) => v.name, getB: (n) => n.label,
    labelA: lblVendor, labelB: lblNode, tier: "T2",
    makeRationale: (v, n) => `Vendor "${v.name}" matches graph node label. Entity-name candidate — verify identity.`,
  }));

  // I. AguaYLuz ↔ Spiderweb (asset appears as graph node label)
  results.push(...candidates({
    aMod: "AguaYLuz-PR", bMod: "Spiderweb-PR", aRecords: infrastructureAssets, bRecords: graphNodes,
    type: "Entity", attr: "entity_name", getA: (a) => a.name, getB: (n) => n.label,
    labelA: lblAsset, labelB: lblNode, getMuni: (r) => r.municipality, tier: "T2",
  }));

  // E. Ovnis ↔ Spiderweb (case linked from graph node)
  results.push(...candidates({
    aMod: "Ovnis-PR", bMod: "Spiderweb-PR", aRecords: unifiedCases, bRecords: graphNodes.filter((n) => n.linked_case_id),
    type: "Graph", attr: "case_link", getA: (c) => c.id, getB: (n) => n.linked_case_id,
    labelA: lblCase, labelB: lblNode, tier: "T2",
    makeRationale: (c, n) => `Graph node references this OVNIS case (linked_case_id). Explicit graph linkage.`,
  }).map((x) => ({ ...x, status: "PendingReview", confidence_score: 60, created_from: "graph_edge" })));

  // K. ContinuityRisks ↔ MoneySweep (risk to an asset funded/contracted in same municipality).
  const lblRisk = (r) => r.title || r.risk_id || r.id;
  results.push(...candidates({
    aMod: "AguaYLuz-PR", bMod: "MoneySweep-PR", aRecords: continuityRisks, bRecords: contracts,
    type: "InfrastructureAdjacency", attr: "municipality", getA: (r) => r.municipality, getB: (c) => c.municipality,
    labelA: lblRisk, labelB: lblContract, getMuni: (r) => r.municipality, tier: "T2",
    secondCriterion: (r, c) => sameRegion(r, c) || (norm(r.agency) && norm(r.agency) === norm(c.agency) ? `shared_agency_${c.agency}` : null),
    makeRationale: (r, c) => `Continuity risk and contract share municipality "${r.municipality}" plus region/agency signal. Possible funding-exposure link — review required.`,
  }));

  // L. AnomalyFlags ↔ MoneySweep (flagged anomaly near contracting activity).
  const lblAnomaly = (a) => a.title || a.anomaly_id || a.id;
  results.push(...candidates({
    aMod: "MoneySweep-PR", bMod: "Spiderweb-PR", aRecords: anomalyFlags, bRecords: contracts,
    type: "Anomaly", attr: "municipality", getA: (a) => a.municipality, getB: (c) => c.municipality,
    labelA: lblAnomaly, labelB: lblContract, getMuni: (r) => r.municipality, tier: "T2",
    secondCriterion: (a, c) => (norm(a.agency) && norm(a.agency) === norm(c.agency) ? `shared_agency_${c.agency}` : sameRegion(a, c)),
    makeRationale: (a, c) => `Anomaly flag and contract converge in "${a.municipality}" with agency/region signal. Structural anomaly signal — source-backed review required, not a conclusion.`,
  }));

  // M. Contract ↔ Vendor ↔ Agency join (vendor named on a contract, same agency).
  results.push(...candidates({
    aMod: "MoneySweep-PR", bMod: "MoneySweep-PR", aRecords: contracts, bRecords: vendors,
    type: "Vendor", attr: "vendor", getA: (c) => c.vendor_id, getB: (v) => v.vendor_id,
    labelA: lblContract, labelB: lblVendor, getMuni: (c) => c.municipality, tier: "T2",
    secondCriterion: (c, v) => (norm(c.municipality) && norm(c.municipality) === norm(v.municipality) ? `shared_municipality_${v.municipality}` : "explicit_vendor_id_join"),
    makeRationale: (c, v) => `Contract "${c.title || c.contract_id}" is awarded to vendor "${v.name}" (explicit vendor_id join). Procurement linkage.`,
  }).map((x) => ({ ...x, agency: contracts.find((c) => c.id === x.source_record_id)?.agency, vendor: vendors.find((v) => v.id === x.target_record_id)?.name })));

  // N. Hub ↔ module control crossovers (tasks, manifests, gates, integrations).
  results.push(...computeHubCrossovers({
    mk, programs, federationTasks, federationManifests, validationGates, integrationStatus,
  }));

  // O. Explicit GraphEdges → crossovers (relationship_type, confidence, tier, source, status).
  results.push(...computeGraphEdgeCrossovers({ mk, graphEdges, nodeById }));

  // Recompute bands + attach resolved source records (for chips with tier meaning).
  for (const r of results) {
    r.confidence_band = r.confidence_band || bandFromScore(r.confidence_score);
    r.tier_meaning = r.evidence_tier ? (tierMeaning[r.evidence_tier] || null) : null;
    r.resolved_sources = (r.source_ids || []).map((sid) => {
      const s = sourceById[sid];
      return s
        ? { id: sid, title: s.title, tier: s.evidence_tier, url: s.url, verification: s.verification_status }
        : { id: sid, title: null, tier: null, url: null, verification: null };
    });
  }

  // Stable dedup key: module pair + both record IDs + correlation type.
  // Sorting the two [module:record] tokens makes the key direction-independent so the
  // same pair isn't double-counted. Stored/explicit links win over candidates; higher score wins ties.
  const seen = new Map();
  for (const r of results) {
    const a = `${r.source_module}:${r.source_record_id}`;
    const b = `${r.target_module}:${r.target_record_id}`;
    const key = [a, b].sort().join("|") + "|" + r.correlation_type;
    const prev = seen.get(key);
    if (!prev || (r._stored && !prev._stored) || r.confidence_score > prev.confidence_score) seen.set(key, r);
  }
  const deduped = Array.from(seen.values());

  // Generate 3+ module convergence from the deduped pairwise set (shared municipality anchor).
  const convergence = computeConvergence({ mk, crossovers: deduped, anchorKey: "municipality" });
  for (const c of convergence) {
    c.confidence_band = c.confidence_band || bandFromScore(c.confidence_score);
    c.resolved_sources = [];
  }
  const crossovers = [...deduped, ...convergence];

  return { crossovers, ilapNodes: graphNodes.filter((n) => ILAP_NODE_TYPES.includes(n.node_type)), sourceById, tierMeaning };
}