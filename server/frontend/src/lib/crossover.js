import { bandFromScore, ILAP_NODE_TYPES } from '@/lib/crossover-config';

const norm = (s) => (s || '').toString().trim().toLowerCase();
const yr = (d) => (d ? new Date(d).getFullYear() : null);
const scoreFor = (confidence) => confidence === 'High' ? 80 : confidence === 'Medium' ? 55 : 35;

function indexByKeys(rows, keys) {
  const out = {};
  for (const row of rows || []) {
    for (const key of keys) {
      const value = row?.[key];
      if (value) out[value] = row;
    }
  }
  return out;
}

function mk(o) {
  const score = o.confidence_score ?? 0;
  return {
    crossover_id: o.crossover_id,
    source_module: o.source_module,
    source_record_id: o.source_record_id,
    source_label: o.source_label || o.source_record_id || '—',
    target_module: o.target_module,
    target_record_id: o.target_record_id,
    target_label: o.target_label || o.target_record_id || '—',
    related_modules: o.related_modules || [o.source_module, o.target_module],
    related_record_ids: o.related_record_ids || [],
    correlation_type: o.correlation_type || 'Other',
    status: o.status || 'Candidate',
    verified: Boolean(o.verified),
    confidence_score: score,
    confidence_band: o.confidence_band || bandFromScore(score),
    rationale: o.rationale || '',
    evidence_tier: o.evidence_tier || null,
    source_ids: o.source_ids || [],
    contradiction_notes: o.contradiction_notes || '',
    municipality: o.municipality || null,
    agency: o.agency || null,
    vendor: o.vendor || null,
    date: o.date || null,
    created_from: o.created_from || 'candidate_match',
    matching_criteria: o.matching_criteria || [],
    _stored: Boolean(o._stored),
    _storedId: o._storedId || null,
  };
}

function fromStored(r, labelFor) {
  return mk({
    crossover_id: r.crossover_id || r.id,
    source_module: r.source_module,
    source_record_id: r.source_record_id,
    source_label: labelFor(r.source_module, r.source_record_id),
    target_module: r.target_module,
    target_record_id: r.target_record_id,
    target_label: labelFor(r.target_module, r.target_record_id),
    related_modules: r.related_modules,
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
    created_from: r.created_from || 'manual',
    matching_criteria: r.matching_criteria,
    _stored: true,
    _storedId: r.id,
  });
}

function fromCorrelationReview(r, eventById, caseById) {
  const ev = eventById[r.airspace_event_id];
  const cs = caseById[r.linked_ovnis_case_id];
  const status = r.status === 'Accepted' ? 'Verified' : r.status === 'Rejected' ? 'Rejected' : r.status === 'Inconclusive' ? 'Contradicted' : 'PendingReview';
  return mk({
    crossover_id: r.review_id || r.id,
    source_module: 'Skywatcher-PR',
    source_record_id: r.airspace_event_id,
    source_label: ev?.title || r.airspace_event_id,
    target_module: 'Ovnis-PR',
    target_record_id: r.linked_ovnis_case_id,
    target_label: cs?.title || cs?.case_code || r.linked_ovnis_case_id || '—',
    correlation_type: r.correlation_type === 'Temporal' ? 'Temporal' : r.correlation_type === 'Spatial' ? 'Geography' : r.correlation_type === 'SourceBased' ? 'SourceEvidence' : 'Entity',
    status,
    verified: r.status === 'Accepted',
    confidence_score: scoreFor(r.confidence),
    rationale: r.rationale,
    evidence_tier: ev?.source_id ? 'T1' : 'T3',
    municipality: ev?.municipality || cs?.municipality,
    date: ev?.event_date,
    contradiction_notes: r.status === 'Inconclusive' ? 'Review marked inconclusive — caveat preserved.' : '',
    created_from: 'correlation_review',
    matching_criteria: ['existing_correlation_review'],
  });
}

function sameYear(aDate, bDate) {
  const ya = yr(aDate);
  const yb = yr(bDate);
  return ya && yb && ya === yb ? `temporal_same_year_${ya}` : null;
}
function sameRegion(a, b) {
  return a?.region && b?.region && norm(a.region) === norm(b.region) ? `shared_region_${a.region}` : null;
}
function candidate({ aMod, bMod, a, b, type, criteria, labelA, labelB, rationale, tier = 'T3' }) {
  const score = criteria.length >= 2 ? 50 : 35;
  return mk({
    crossover_id: `cand-${type}-${a.id || a.flag_id || a.risk_id}-${b.id || b.contract_id || b.asset_id}`,
    source_module: aMod,
    source_record_id: a.id || a.flag_id || a.risk_id || a.contract_id || a.asset_id,
    source_label: labelA(a),
    target_module: bMod,
    target_record_id: b.id || b.contract_id || b.asset_id,
    target_label: labelB(b),
    correlation_type: type,
    status: 'Candidate',
    confidence_score: score,
    rationale,
    evidence_tier: tier,
    municipality: a.municipality || b.municipality,
    agency: a.agency || b.agency,
    date: a.event_date || a.award_date || b.award_date,
    matching_criteria: criteria,
  });
}

export function computeCrossovers(data, { includeTest = false } = {}) {
  const {
    airspaceEvents = [], unifiedCases = [], infrastructureAssets = [], continuityRisks = [],
    contracts = [], vendors = [], anomalyFlags = [], graphNodes = [], graphEdges = [],
    unifiedSources = [], correlationReviews = [], crossoverLinks = [],
    programs = [], federationTasks = [], federationManifests = [], validationGates = [], integrationStatus = [], evidenceStandards = [],
  } = data || {};

  const eventById = indexByKeys(airspaceEvents, ['id', 'event_id']);
  const caseById = indexByKeys(unifiedCases, ['id', 'case_id', 'case_code']);
  const assetById = indexByKeys(infrastructureAssets, ['id', 'asset_id']);
  const contractById = indexByKeys(contracts, ['id', 'contract_id']);
  const sourceById = indexByKeys(unifiedSources, ['id', 'source_id']);
  const tierMeaning = Object.fromEntries((evidenceStandards || []).filter((s) => s.tier).map((s) => [s.tier, { label: s.label, definition: s.definition, weight: s.weight }]));

  const enrichedContinuityRisks = continuityRisks.map((risk) => {
    const asset = assetById[risk.asset_id] || {};
    return { ...risk, title: risk.title || risk.summary || risk.risk_id, municipality: risk.municipality || asset.municipality || null, region: risk.region || asset.region || null, agency: risk.agency || asset.owner_agency || asset.operator || null };
  });
  const enrichedAnomalyFlags = anomalyFlags.map((flag) => {
    const contract = contractById[flag.contract_id] || {};
    return { ...flag, title: flag.title || `${flag.flag_type || 'Anomaly'}: ${contract.title || flag.contract_id || flag.flag_id}`, anomaly_id: flag.anomaly_id || flag.flag_id, municipality: flag.municipality || contract.municipality || null, region: flag.region || contract.region || null, agency: flag.agency || contract.agency || null };
  });

  const labelFor = (_mod, id) => {
    const lists = [airspaceEvents, unifiedCases, infrastructureAssets, contracts, vendors, graphNodes];
    for (const list of lists) {
      const hit = list.find((r) => [r.id, r.event_id, r.case_id, r.case_code, r.asset_id, r.contract_id, r.vendor_id, r.node_id].includes(id));
      if (hit) return hit.title || hit.name || hit.label || id;
    }
    return id || '—';
  };

  const results = [];
  for (const r of (includeTest ? crossoverLinks : crossoverLinks.filter((x) => !x.test_record))) results.push(fromStored(r, labelFor));
  for (const r of correlationReviews) results.push(fromCorrelationReview(r, eventById, caseById));

  const lblEvent = (e) => e.title || e.event_id || e.id;
  const lblCase = (c) => c.title || c.case_code || c.case_id || c.id;
  const lblAsset = (a) => a.name || a.asset_id || a.id;
  const lblContract = (c) => c.title || c.contract_id || c.id;
  const lblVendor = (v) => v.name || v.vendor_id || v.id;
  const lblNode = (n) => n.label || n.node_id || n.id;
  const lblRisk = (r) => r.title || r.risk_id || r.id;
  const lblAnomaly = (a) => a.title || a.flag_id || a.anomaly_id || a.id;

  const pushGeo = (aMod, bMod, aRows, bRows, labelA, labelB, type = 'Geography') => {
    for (const a of aRows) for (const b of bRows) {
      if (!a.municipality || norm(a.municipality) !== norm(b.municipality)) continue;
      const second = sameRegion(a, b) || sameYear(a.event_date || a.award_date, b.event_date || b.award_date);
      if (!second) continue;
      results.push(candidate({ aMod, bMod, a, b, type, labelA, labelB, tier: 'T2', criteria: ['shared_municipality', second], rationale: `${labelA(a)} and ${labelB(b)} share municipality ${a.municipality} plus ${second}. Candidate only; review required.` }));
    }
  };

  pushGeo('Skywatcher-PR', 'AguaYLuz-PR', airspaceEvents, infrastructureAssets, lblEvent, lblAsset);
  pushGeo('Skywatcher-PR', 'MoneySweep-PR', airspaceEvents, contracts, lblEvent, lblContract);
  pushGeo('Ovnis-PR', 'AguaYLuz-PR', unifiedCases, infrastructureAssets, lblCase, lblAsset);
  pushGeo('Ovnis-PR', 'MoneySweep-PR', unifiedCases, contracts, lblCase, lblContract);
  pushGeo('AguaYLuz-PR', 'MoneySweep-PR', infrastructureAssets, contracts, lblAsset, lblContract, 'InfrastructureAdjacency');

  for (const risk of enrichedContinuityRisks) for (const contract of contracts) {
    if (!risk.municipality || norm(risk.municipality) !== norm(contract.municipality)) continue;
    const second = sameRegion(risk, contract) || (norm(risk.agency) && norm(risk.agency) === norm(contract.agency) ? `shared_agency_${contract.agency}` : null);
    if (!second) continue;
    results.push(candidate({ aMod: 'AguaYLuz-PR', bMod: 'MoneySweep-PR', a: risk, b: contract, type: 'InfrastructureAdjacency', labelA: lblRisk, labelB: lblContract, tier: 'T2', criteria: ['asset_join_municipality', second], rationale: `Continuity risk ${risk.risk_id || risk.id} joins through InfrastructureAssets.asset_id and converges with contract ${contract.contract_id || contract.id}.` }));
  }

  for (const flag of enrichedAnomalyFlags) for (const contract of contracts) {
    if (flag.contract_id && contract.contract_id && flag.contract_id !== contract.contract_id) continue;
    if (!flag.municipality || norm(flag.municipality) !== norm(contract.municipality)) continue;
    const second = norm(flag.agency) && norm(flag.agency) === norm(contract.agency) ? `shared_agency_${contract.agency}` : sameRegion(flag, contract);
    if (!second) continue;
    results.push(candidate({ aMod: 'MoneySweep-PR', bMod: 'MoneySweep-PR', a: flag, b: contract, type: 'Anomaly', labelA: lblAnomaly, labelB: lblContract, tier: 'T2', criteria: ['contract_id_join', second], rationale: `Anomaly flag ${flag.flag_id || flag.id} is linked to contract ${contract.contract_id || contract.id}. MoneySweep internal anomaly signal; not a Spiderweb convergence.` }));
  }

  for (const contract of contracts) for (const vendor of vendors) {
    if (!contract.vendor_id || norm(contract.vendor_id) !== norm(vendor.vendor_id)) continue;
    results.push(candidate({ aMod: 'MoneySweep-PR', bMod: 'MoneySweep-PR', a: contract, b: vendor, type: 'Vendor', labelA: lblContract, labelB: lblVendor, tier: 'T2', criteria: ['explicit_vendor_id_join'], rationale: `Contract ${contract.contract_id || contract.id} is awarded to vendor ${vendor.name || vendor.vendor_id}.` }));
  }

  for (const node of graphNodes) {
    if (ILAP_NODE_TYPES.includes(node.node_type)) {
      results.push(mk({ crossover_id: `ilap-${node.node_id || node.id}`, source_module: 'Spiderweb-PR', source_record_id: node.node_id || node.id, target_module: 'Hub', target_record_id: 'ilap-review', correlation_type: 'LandDevelopment', status: 'Candidate', confidence_score: scoreFor(node.confidence), rationale: node.summary || 'ILAP/POI node surfaced for Hub review.', evidence_tier: 'T3', municipality: node.municipality, created_from: 'graph_edge', matching_criteria: ['ilap_node_type'] }));
    }
  }

  for (const edge of graphEdges) {
    results.push(mk({ crossover_id: `edge-${edge.edge_id || edge.id}`, source_module: 'Spiderweb-PR', source_record_id: edge.source_node_id, source_label: edge.source_node_id, target_module: 'Spiderweb-PR', target_record_id: edge.target_node_id, target_label: edge.target_node_id, correlation_type: edge.relationship_type === 'Contradicts' ? 'Contradiction' : 'Graph', status: edge.status === 'Accepted' ? 'Verified' : edge.status === 'Rejected' ? 'Rejected' : edge.status === 'Disputed' ? 'Contradicted' : 'PendingReview', verified: edge.status === 'Accepted', confidence_score: scoreFor(edge.confidence), rationale: edge.rationale || `Explicit graph edge ${edge.relationship_type}.`, evidence_tier: edge.evidence_tier || 'T2', source_ids: edge.source_id ? [edge.source_id] : [], created_from: 'graph_edge', matching_criteria: ['explicit_graph_edge'] }));
  }

  const programModule = Object.fromEntries(programs.map((p) => [p.program_id || p.id, p.name || p.module || 'Hub']));
  const hubRows = [...federationTasks, ...federationManifests, ...validationGates, ...integrationStatus];
  for (const row of hubRows) {
    const module = programModule[row.program_id] || row.module || 'Hub';
    if (module === 'Hub' || module === 'INTSYS-PR') continue;
    const rid = row.task_id || row.manifest_id || row.gate_id || row.integration_id || row.id;
    results.push(mk({ crossover_id: `hub-${rid}`, source_module: 'Hub', source_record_id: rid, target_module: module, target_record_id: row.program_id || module, correlation_type: 'Other', status: row.status === 'Passed' || row.status === 'Connected' || row.status === 'Ready' ? 'Verified' : row.status === 'Blocked' ? 'NeedsSource' : 'PendingReview', confidence_score: 60, rationale: `Hub control-plane record ${rid} applies to ${module}.`, evidence_tier: 'T1', created_from: 'explicit_link', matching_criteria: ['hub_control_record'] }));
  }

  for (const r of results) {
    r.confidence_band = r.confidence_band || bandFromScore(r.confidence_score);
    r.tier_meaning = r.evidence_tier ? (tierMeaning[r.evidence_tier] || null) : null;
    r.resolved_sources = (r.source_ids || []).map((sid) => sourceById[sid] ? { id: sid, title: sourceById[sid].title, tier: sourceById[sid].evidence_tier, url: sourceById[sid].url, verification: sourceById[sid].verification_status } : { id: sid, title: null, tier: null, url: null, verification: null });
  }

  const seen = new Map();
  for (const r of results) {
    const key = [`${r.source_module}:${r.source_record_id}`, `${r.target_module}:${r.target_record_id}`].sort().join('|') + `|${r.correlation_type}`;
    const prev = seen.get(key);
    if (!prev || (r._stored && !prev._stored) || r.confidence_score > prev.confidence_score) seen.set(key, r);
  }

  const crossovers = Array.from(seen.values());
  const ilapNodes = graphNodes.filter((n) => ILAP_NODE_TYPES.includes(n.node_type));
  return { crossovers, ilapNodes, sourceById };
}
