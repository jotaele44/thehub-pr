// Multi-module (3+) convergence generation.
// Where 3+ modules overlap on the SAME shared attribute (e.g. same municipality across an
// airspace event + infrastructure asset + contract), we synthesize a convergence record.
// Convergence is a structural signal requiring source-backed review — never a conclusion,
// always emitted as a Candidate.

const norm = (s) => (s || "").toString().trim().toLowerCase();

// Group already-computed pairwise crossovers by a shared anchor (municipality) and, when
// 3+ distinct modules share that anchor, emit one convergence record listing all of them.
export function computeConvergence({ mk, crossovers, anchorKey = "municipality" }) {
  const groups = {};
  for (const c of crossovers) {
    const anchor = norm(c[anchorKey]);
    if (!anchor) continue;
    (groups[anchor] ||= []).push(c);
  }

  const out = [];
  for (const [anchor, rows] of Object.entries(groups)) {
    const modules = new Set();
    const recordIds = new Set();
    const types = new Set();
    let topScore = 0;
    for (const r of rows) {
      modules.add(r.source_module);
      modules.add(r.target_module);
      if (r.source_record_id) recordIds.add(`${r.source_module}:${r.source_record_id}`);
      if (r.target_record_id) recordIds.add(`${r.target_module}:${r.target_record_id}`);
      types.add(r.correlation_type);
      topScore = Math.max(topScore, r.confidence_score || 0);
    }
    if (modules.size < 3) continue; // convergence requires 3+ modules on the same anchor

    const mods = Array.from(modules).sort();
    const display = rows[0][anchorKey];
    out.push(mk({
      crossover_id: `conv-${anchorKey}-${anchor}`,
      source_module: mods[0],
      source_record_id: `convergence:${anchor}`,
      source_label: `${mods.length}-module convergence`,
      target_module: mods[1],
      target_record_id: `convergence:${anchor}`,
      target_label: display,
      related_modules: mods,
      related_record_ids: Array.from(recordIds),
      correlation_type: "Geography",
      status: "Candidate",
      verified: false,
      confidence_score: Math.min(topScore, 65),
      rationale: `${mods.length} modules (${mods.join(", ")}) overlap at "${display}" across ${recordIds.size} records. Multi-module convergence — structural signal requiring source-backed review, not a conclusion.`,
      evidence_tier: "T2",
      municipality: display,
      created_from: "candidate_match",
      matching_criteria: [`convergence_${anchorKey}`, `modules_${mods.length}`],
    }));
  }
  return out;
}

// Normalize explicit GraphEdges into crossovers. Edges carry relationship_type, confidence,
// evidence_tier, source_id and review status — all explicit, so these are PendingReview/Verified
// per the edge's own status rather than inferred candidates.
export function computeGraphEdgeCrossovers({ mk, graphEdges, nodeById }) {
  const out = [];
  const statusMap = { Accepted: "Verified", Rejected: "Rejected", Disputed: "Contradicted", Reviewing: "PendingReview", Proposed: "PendingReview" };
  const scoreFor = (c) => (c === "High" ? 80 : c === "Medium" ? 55 : 35);

  for (const e of graphEdges) {
    const src = nodeById[e.source_node_id];
    const tgt = nodeById[e.target_node_id];
    if (!src || !tgt) continue;
    out.push(mk({
      crossover_id: `edge-${e.edge_id || e.id}`,
      source_module: "Spiderweb-PR",
      source_record_id: e.source_node_id,
      source_label: src.label || e.source_node_id,
      target_module: "Spiderweb-PR",
      target_record_id: e.target_node_id,
      target_label: tgt.label || e.target_node_id,
      correlation_type: e.relationship_type === "Contradicts" ? "Contradiction" : "Graph",
      status: statusMap[e.status] || "PendingReview",
      verified: e.status === "Accepted",
      confidence_score: scoreFor(e.confidence),
      rationale: `Explicit graph edge: ${src.label || e.source_node_id} —[${e.relationship_type}]→ ${tgt.label || e.target_node_id}. ${e.rationale || ""}`.trim(),
      evidence_tier: e.evidence_tier || "T2",
      source_ids: e.source_id ? [e.source_id] : [],
      contradiction_notes: e.relationship_type === "Contradicts" ? "Edge encodes a contradiction relationship — caveat preserved." : "",
      created_from: "graph_edge",
      matching_criteria: ["explicit_graph_edge", `relationship_${e.relationship_type}`],
    }));
  }
  return out;
}