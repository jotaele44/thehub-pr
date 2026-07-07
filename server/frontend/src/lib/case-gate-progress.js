// Case validation-stage progress derived from a case row + the UnifiedSources
// ledger. Consumed by CaseGateTracker; returns
// { stageIndex, percent, label, bestTier, verifiedCount, sourceCount, blocked }.

export const CASE_STAGES = [
  { key: "new", label: "New" },
  { key: "sourced", label: "Sourced" },
  { key: "reviewing", label: "Reviewing" },
  { key: "verified", label: "Verified" },
  { key: "corroborated", label: "Corroborated" },
];

const unwrap = (row) => (row && row.data ? { ...row.data, id: row.id ?? row.data.id } : row);

const TIER_RANK = { T1: 1, T2: 2, T3: 3, T4: 4 };

const sourcesForCase = (caseRow, sources = []) => {
  const ids = new Set(
    [caseRow?.case_id, caseRow?.case_code, caseRow?.id].filter(Boolean).map(String)
  );
  return sources.map(unwrap).filter((s) => {
    const ref = s?.case_id || s?.linked_case_id || s?.related_case_id;
    return ref && ids.has(String(ref));
  });
};

export function getCaseGateProgress(caseRow, sources = []) {
  const linked = sourcesForCase(caseRow, sources);
  const sourceCount = linked.length;
  const verifiedCount = linked.filter((s) => s.verification_status === "Verified").length;

  let bestTier = null;
  for (const s of linked) {
    const t = s.evidence_tier;
    if (t && TIER_RANK[t] && (!bestTier || TIER_RANK[t] < TIER_RANK[bestTier])) bestTier = t;
  }

  const status = caseRow?.status || "New";
  const blocked = status === "Contradicted";

  let stageIndex = 0;
  if (status === "Corroborated" || status === "Archived") stageIndex = 4;
  else if (verifiedCount > 0) stageIndex = 3;
  else if (status === "Reviewing") stageIndex = 2;
  else if (sourceCount > 0) stageIndex = 1;

  const percent = blocked ? 0 : Math.round((stageIndex / (CASE_STAGES.length - 1)) * 100);
  const label = CASE_STAGES[stageIndex].label;

  return { stageIndex, percent, label, bestTier, verifiedCount, sourceCount, blocked };
}
