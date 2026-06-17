import { useMemo, useState } from "react";
import { useEntityData } from "@/hooks/useEntityData";
import { computeCrossovers } from "@/lib/crossover";
import { MODULE_PAIRS, pairKey } from "@/lib/crossover-config";

const VERIFIED_SET = new Set(["Verified"]);
const PENDING_SET = new Set(["Candidate", "PendingReview", "NeedsSource"]);
const CONTRA_SET = new Set(["Contradicted", "Rejected"]);

const EMPTY_FILTERS = {
  bucket: "all", // all | verified | pending | contradicted
  band: "all", tier: "all", municipality: "all", pair: "all", type: "all", search: "",
  agency: "all", vendor: "all", dateFrom: "", dateTo: "",
};

export function useCrossover() {
  const [filters, setFilters] = useState(EMPTY_FILTERS);

  // Load every contributing entity (read-only; ownership preserved).
  const ae = useEntityData("AirspaceEvents", "-created_date");
  const uc = useEntityData("UnifiedCases", "-created_date");
  const ia = useEntityData("InfrastructureAssets", "-created_date");
  const cr = useEntityData("ContinuityRisks", "-created_date");
  const co = useEntityData("Contracts", "-created_date");
  const ve = useEntityData("Vendors", "-created_date");
  const af = useEntityData("AnomalyFlags", "-created_date");
  const gn = useEntityData("GraphNodes", "-created_date");
  const ge = useEntityData("GraphEdges", "-created_date");
  const us = useEntityData("UnifiedSources", "-created_date");
  const rv = useEntityData("CorrelationReviews", "-created_date");
  const cx = useEntityData("CrossoverLinks", "-created_date");
  // Hub-control + governance ledgers (Hub ↔ module crossovers + tier definitions).
  const pg = useEntityData("Programs", "-created_date");
  const ft = useEntityData("FederationTasks", "-created_date");
  const fm = useEntityData("FederationManifest", "-created_date");
  const vg = useEntityData("ValidationGates", "-created_date");
  const ist = useEntityData("IntegrationStatus", "-created_date");
  const es = useEntityData("EvidenceStandards", "-created_date");

  const loaders = [ae, uc, ia, cr, co, ve, af, gn, ge, us, rv, cx, pg, ft, fm, vg, ist, es];
  const isLoading = loaders.some((l) => l.isLoading);
  const isError = loaders.some((l) => l.isError);

  const { crossovers, ilapNodes } = useMemo(() => computeCrossovers({
    airspaceEvents: ae.rows, unifiedCases: uc.rows, infrastructureAssets: ia.rows, continuityRisks: cr.rows,
    contracts: co.rows, vendors: ve.rows, anomalyFlags: af.rows, graphNodes: gn.rows, graphEdges: ge.rows,
    unifiedSources: us.rows, correlationReviews: rv.rows, crossoverLinks: cx.rows,
    programs: pg.rows, federationTasks: ft.rows, federationManifests: fm.rows, validationGates: vg.rows,
    integrationStatus: ist.rows, evidenceStandards: es.rows,
  }), [ae.rows, uc.rows, ia.rows, cr.rows, co.rows, ve.rows, af.rows, gn.rows, ge.rows, us.rows, rv.rows, cx.rows, pg.rows, ft.rows, fm.rows, vg.rows, ist.rows, es.rows]);

  const municipalities = useMemo(
    () => Array.from(new Set(crossovers.map((c) => c.municipality).filter(Boolean))).sort(),
    [crossovers]
  );
  const agencies = useMemo(
    () => Array.from(new Set(crossovers.map((c) => c.agency).filter(Boolean))).sort(),
    [crossovers]
  );
  const vendorsList = useMemo(
    () => Array.from(new Set(crossovers.map((c) => c.vendor).filter(Boolean))).sort(),
    [crossovers]
  );

  const filtered = useMemo(() => crossovers.filter((c) => {
    if (filters.bucket === "verified" && !VERIFIED_SET.has(c.status)) return false;
    if (filters.bucket === "pending" && !PENDING_SET.has(c.status)) return false;
    if (filters.bucket === "contradicted" && !CONTRA_SET.has(c.status)) return false;
    if (filters.band !== "all" && c.confidence_band !== filters.band) return false;
    if (filters.tier !== "all" && c.evidence_tier !== filters.tier) return false;
    if (filters.municipality !== "all" && c.municipality !== filters.municipality) return false;
    if (filters.type !== "all" && c.correlation_type !== filters.type) return false;
    if (filters.pair !== "all" && pairKey(c.source_module, c.target_module) !== filters.pair) return false;
    if (filters.agency !== "all" && c.agency !== filters.agency) return false;
    if (filters.vendor !== "all" && c.vendor !== filters.vendor) return false;
    if (filters.dateFrom && (!c.date || c.date < filters.dateFrom)) return false;
    if (filters.dateTo && (!c.date || c.date > filters.dateTo)) return false;
    if (filters.search) {
      const q = filters.search.toLowerCase();
      const hay = `${c.source_label} ${c.target_label} ${c.rationale} ${c.municipality || ""}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  }), [crossovers, filters]);

  // Summary derived from ALL crossovers (uncertainty stays visible).
  const summary = useMemo(() => {
    const pairSet = new Set(crossovers.map((c) => pairKey(c.source_module, c.target_module)));
    return {
      verified: crossovers.filter((c) => VERIFIED_SET.has(c.status)).length,
      pending: crossovers.filter((c) => PENDING_SET.has(c.status)).length,
      contradicted: crossovers.filter((c) => CONTRA_SET.has(c.status)).length,
      highConfidence: crossovers.filter((c) => c.confidence_band === "High").length,
      modulePairs: pairSet.size,
      multiModule: crossovers.filter((c) => (c.related_modules?.length || 2) >= 3).length,
      missingSource: crossovers.filter((c) => !(c.source_ids?.length) && c.status !== "Verified").length,
      total: crossovers.length,
    };
  }, [crossovers]);

  // Matrix rows for every module pair.
  const matrix = useMemo(() => MODULE_PAIRS.map(([a, b]) => {
    const key = pairKey(a, b);
    const rows = crossovers.filter((c) => pairKey(c.source_module, c.target_module) === key);
    const tierCount = {};
    const typeCount = {};
    let topScore = 0;
    for (const r of rows) {
      if (r.evidence_tier) tierCount[r.evidence_tier] = (tierCount[r.evidence_tier] || 0) + 1;
      typeCount[r.correlation_type] = (typeCount[r.correlation_type] || 0) + 1;
      topScore = Math.max(topScore, r.confidence_score || 0);
    }
    const top = (obj) => Object.entries(obj).sort((x, y) => y[1] - x[1])[0]?.[0] || "—";
    return {
      a, b, key,
      count: rows.length,
      verified: rows.filter((r) => VERIFIED_SET.has(r.status)).length,
      pending: rows.filter((r) => PENDING_SET.has(r.status)).length,
      contradicted: rows.filter((r) => CONTRA_SET.has(r.status)).length,
      topScore,
      dominantTier: top(tierCount),
      commonType: top(typeCount),
      gaps: rows.filter((r) => !(r.source_ids?.length) && r.status !== "Verified").length,
    };
  }), [crossovers]);

  return {
    isLoading, isError,
    crossovers, filtered, ilapNodes, summary, matrix, municipalities, agencies, vendorsList,
    filters, setFilters, resetFilters: () => setFilters(EMPTY_FILTERS),
    pairKey,
  };
}