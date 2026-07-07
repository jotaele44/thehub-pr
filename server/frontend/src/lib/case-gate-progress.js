// Pure logic: derive a case's movement through validation stages from its
// own status and the evidence tiers / verification of its linked sources.
// No conclusions are hard-coded — stages reflect review progression only.

// Ordered validation stages a case moves through.
export const CASE_STAGES = [
  { key: "Intake", label: "Intake" },
  { key: "SourcesLinked", label: "Sources Linked" },
  { key: "EvidenceTiered", label: "Evidence Tiered" },
  { key: "Verified", label: "Verified" },
  { key: "Resolved", label: "Resolved" },
];

const TIER_RANK = { T4: 1, T3: 2, T2: 3, T1: 4 };

// Returns { stageIndex, percent, label, bestTier, verifiedCount, sourceCount, blocked }
export function getCaseGateProgress(caseRow, allSources) {
  const sources = (allSources || []).filter((s) => s.linked_case_id === caseRow.case_id);
  const sourceCount = sources.length;

  const verifiedCount = sources.filter((s) => s.verification_status === "Verified").length;
  const tiers = sources.map((s) => s.evidence_tier).filter(Boolean);
  const bestTier = tiers.sort((a, b) => (TIER_RANK[b] || 0) - (TIER_RANK[a] || 0))[0] || null;

  // A case is blocked/contradicted — surfaced, never advanced.
  const blocked = caseRow.status === "Contradicted";

  let stageIndex = 0; // Intake
  if (sourceCount > 0) stageIndex = 1; // SourcesLinked
  if (bestTier && (TIER_RANK[bestTier] || 0) >= 3) stageIndex = 2; // EvidenceTiered (T2+)
  if (verifiedCount > 0) stageIndex = 3; // Verified
  if (caseRow.status === "Corroborated" || caseRow.status === "Archived") stageIndex = 4; // Resolved

  const percent = Math.round((stageIndex / (CASE_STAGES.length - 1)) * 100);

  return {
    stageIndex,
    percent,
    label: CASE_STAGES[stageIndex].label,
    bestTier,
    verifiedCount,
    sourceCount,
    blocked,
  };
}