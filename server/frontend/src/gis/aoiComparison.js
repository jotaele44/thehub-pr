// Negative controls and regional-prevalence normalization (FDX-028/029; directive
// §32 and §46): "is this relationship more common inside the target AOI than in
// comparable background areas?" A study AOI is compared with one or more control
// AOIs by records per km², per (producer, stream, category). Every result is a
// BACKGROUND COMPARISON, never a finding.
//
//  - Membership uses only points whose producer declared a placed point
//    (OBSERVED_POINT, INTERPRETED_POINT). A REPRESENTATIVE_POINT is a stand-in
//    (for example a municipio centroid): inside an AOI it is counted separately
//    as "membership not determined", never as a record located there (§47).
//  - AOIs must be pairwise disjoint, so no record or area is counted twice.
//  - Counts are over the served store, which may be a bounded sample; the
//    caller states that (storeBasis.js), and the receipt carries it.
import { SPATIAL_CONTRACT, bboxAreaM2, boundaryName, foldPlaceName, geometryContains, parseBboxText, polygonAreaM2 } from './propertyMap';
import { describeStore } from './storeBasis';

export const COMPARISON_CONTRACT = 'aoi-comparison-v1';
export const NOT_A_FINDING = 'BACKGROUND COMPARISON — not a finding';
export const MIN_COMBINED_RECORDS = 5;
const PLACED = new Set(['OBSERVED_POINT', 'INTERPRETED_POINT']);
const AREA_METHOD = 'spherical polygon area on the reference sphere (radius 6371008.8 m)';
const MAX_EXACT_N = 1_000_000;

// ── Exact binomial test and Clopper-Pearson interval ─────────────────────────

const logFactorials = [0];
function logChoose(n, k) {
  while (logFactorials.length <= n) logFactorials.push(logFactorials[logFactorials.length - 1] + Math.log(logFactorials.length));
  return logFactorials[n] - logFactorials[k] - logFactorials[n - k];
}

function logPmf(k, n, p) {
  if (p <= 0) return k === 0 ? 0 : -Infinity;
  if (p >= 1) return k === n ? 0 : -Infinity;
  return logChoose(n, k) + k * Math.log(p) + (n - k) * Math.log(1 - p);
}

function guard(n) {
  if (!Number.isInteger(n) || n < 0 || n > MAX_EXACT_N) throw new Error('too many records for the exact test');
}

function binomialCdf(k, n, p) {
  let sum = 0;
  for (let index = 0; index <= k; index += 1) sum += Math.exp(logPmf(index, n, p));
  return Math.min(1, sum);
}

// Two-sided exact p-value, summing every outcome no more likely than the observed one (R's binom.test).
export function binomialPValue(k, n, p) {
  guard(n);
  const observed = logPmf(k, n, p);
  const limit = observed + Math.log(1 + 1e-7);
  let sum = 0;
  for (let index = 0; index <= n; index += 1) {
    const value = logPmf(index, n, p);
    if (value <= limit) sum += Math.exp(value);
  }
  return Math.min(1, sum);
}

// The p at which `f` crosses zero, by bisection (f is monotone on [0, 1]).
function solve(f, increasing) {
  let low = 0;
  let high = 1;
  for (let step = 0; step < 80; step += 1) {
    const mid = (low + high) / 2;
    if ((f(mid) < 0) === increasing) low = mid; else high = mid;
  }
  return (low + high) / 2;
}

export function clopperPearson(k, n, alpha = 0.05) {
  guard(n);
  const lower = k === 0 ? 0 : solve((p) => 1 - binomialCdf(k - 1, n, p) - alpha / 2, true);
  const upper = k === n ? 1 : solve((p) => binomialCdf(k, n, p) - alpha / 2, false);
  return [lower, upper];
}

// Rate ratio (study per km² over control per km²) interval from the conditional
// binomial: ratio = p / (1 - p) * controlArea / studyArea.
export function rateRatioInterval(k, n, studyKm2, controlsKm2) {
  const scale = controlsKm2 / studyKm2;
  return clopperPearson(k, n).map((p) => (p >= 1 ? Infinity : (p / (1 - p)) * scale));
}

// ── AOIs ─────────────────────────────────────────────────────────────────────

function aoi(id, label, kind, geometry, areaM2, source) {
  return Object.freeze({ id, label, kind, geometry, areaM2, areaMethod: AREA_METHOD, source });
}

// A p-value as shown: three decimals, and never a bare 0.000, which would read as a certainty.
export function formatP(p) {
  return p < 0.001 ? '<0.001' : p.toFixed(3);
}

export function aoiFromBbox(id, label, text) {
  const [west, south, east, north] = parseBboxText(text);
  const geometry = { type: 'Polygon', coordinates: [[[west, south], [east, south], [east, north], [west, north], [west, south]]] };
  return aoi(id, label, 'bbox', geometry, bboxAreaM2([west, south, east, north]), 'typed or drawn bounding box');
}

// A municipio by its recorded name (accent, case and "Municipio" folded, as the
// Property Map joins them); a name that matches no boundary is refused.
export function aoiFromMunicipio(id, name, boundaries) {
  if (!boundaries?.features) throw new Error('the municipio boundary layer is not loaded');
  const wanted = foldPlaceName(name);
  const hit = boundaries.features.find((item) => foldPlaceName(boundaryName(item.properties)) === wanted);
  if (!hit) throw new Error(`the loaded boundary layer has no municipio named "${name}"`);
  return aoi(id, boundaryName(hit.properties), 'municipio', hit.geometry, polygonAreaM2(hit.geometry),
    'TIGERweb municipios 2025 (census-tigerweb-pr-municipios-2025)');
}

function outerRings(geometry) {
  if (geometry?.type === 'Polygon') return [geometry.coordinates[0]];
  if (geometry?.type === 'MultiPolygon') return geometry.coordinates.map((rings) => rings[0]);
  return [];
}

function ringBox(ring) {
  const xs = ring.map((point) => point[0]);
  const ys = ring.map((point) => point[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

function orientation([ax, ay], [bx, by], [cx, cy]) {
  const value = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax);
  return value === 0 ? 0 : value > 0 ? 1 : -1;
}

function onSegment([ax, ay], [bx, by], [cx, cy]) {
  return Math.min(ax, bx) <= cx && cx <= Math.max(ax, bx) && Math.min(ay, by) <= cy && cy <= Math.max(ay, by);
}

// True when segments p1-p2 and p3-p4 cross or touch.
function segmentsMeet(p1, p2, p3, p4) {
  const o1 = orientation(p1, p2, p3);
  const o2 = orientation(p1, p2, p4);
  const o3 = orientation(p3, p4, p1);
  const o4 = orientation(p3, p4, p2);
  if (o1 !== o2 && o3 !== o4) return true;
  return (o1 === 0 && onSegment(p1, p2, p3)) || (o2 === 0 && onSegment(p1, p2, p4))
    || (o3 === 0 && onSegment(p3, p4, p1)) || (o4 === 0 && onSegment(p3, p4, p2));
}

function ringsMeet(a, b) {
  const [aw, as, ae, an] = ringBox(a);
  const [bw, bs, be, bn] = ringBox(b);
  if (aw > be || bw > ae || as > bn || bs > an) return false;
  for (let i = 0; i < a.length - 1; i += 1) {
    for (let j = 0; j < b.length - 1; j += 1) {
      if (segmentsMeet(a[i], a[i + 1], b[j], b[j + 1])) return true;
    }
  }
  return false;
}

// Whether two areas share any point: crossing or touching edges, or one inside the other.
export function aoisOverlap(a, b) {
  const ringsA = outerRings(a);
  const ringsB = outerRings(b);
  for (const ra of ringsA) {
    for (const rb of ringsB) {
      if (ringsMeet(ra, rb)) return true;
    }
  }
  return ringsA.some((ring) => geometryContains(b, ring[0][0], ring[0][1]))
    || ringsB.some((ring) => geometryContains(a, ring[0][0], ring[0][1]));
}

// ── Comparison ───────────────────────────────────────────────────────────────

function problems(study, controls) {
  const errors = [];
  if (!controls.length) errors.push('At least one control AOI is required.');
  for (const item of [study, ...controls]) {
    if (!(item.areaM2 > 0)) errors.push(`${item.label} has no area.`);
  }
  if (errors.length) return errors;
  for (const control of controls) {
    if (aoisOverlap(study.geometry, control.geometry)) {
      errors.push(`Control "${control.label}" overlaps the study AOI "${study.label}"; controls must be disjoint from it.`);
    }
  }
  for (let i = 0; i < controls.length; i += 1) {
    for (let j = i + 1; j < controls.length; j += 1) {
      if (aoisOverlap(controls[i].geometry, controls[j].geometry)) {
        errors.push(`Controls "${controls[i].label}" and "${controls[j].label}" overlap; a record or area would be counted twice.`);
      }
    }
  }
  return errors;
}

const blank = () => ({ count: 0, undetermined: 0 });

function statistics(studyCount, controlCount, studyKm2, controlsKm2) {
  const n = studyCount + controlCount;
  if (n < MIN_COMBINED_RECORDS) return { status: 'TOO_FEW', ratio: null, ci: null, p: null };
  const share = studyKm2 / (studyKm2 + controlsKm2);
  return {
    status: 'COMPARED',
    ratio: controlCount === 0 ? Infinity : (studyCount / studyKm2) / (controlCount / controlsKm2),
    ci: rateRatioInterval(studyCount, n, studyKm2, controlsKm2),
    p: binomialPValue(studyCount, n, share),
  };
}

// features: spatial features (point features with declared precision); study:
// one AOI; controls: AOIs disjoint from it and from each other.
export function compareAois({ features, study, controls }) {
  const errors = problems(study, controls);
  if (errors.length) return { errors };
  const cells = new Map();
  let outside = 0;
  for (const item of features) {
    const [lon, lat] = item.geometry.coordinates;
    const home = [study, ...controls].find((area) => geometryContains(area.geometry, lon, lat));
    if (!home) { outside += 1; continue; }
    const properties = item.properties;
    const key = `${properties.producer}|${properties.stream}|${properties.category}`;
    if (!cells.has(key)) cells.set(key, { producer: properties.producer, stream: properties.stream, category: properties.category, byAoi: new Map() });
    const cell = cells.get(key);
    if (!cell.byAoi.has(home.id)) cell.byAoi.set(home.id, blank());
    const tally = cell.byAoi.get(home.id);
    if (PLACED.has(properties.geometry_precision)) tally.count += 1; else tally.undetermined += 1;
  }
  const studyKm2 = study.areaM2 / 1e6;
  const controlsKm2 = controls.reduce((total, control) => total + control.areaM2, 0) / 1e6;
  const sum = (cell, field) => controls.reduce((total, control) => total + (cell.byAoi.get(control.id)?.[field] || 0), 0);
  const rows = [...cells.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([key, cell]) => {
    const studyTally = cell.byAoi.get(study.id) || blank();
    const controlCount = sum(cell, 'count');
    return {
      key, producer: cell.producer, stream: cell.stream, category: cell.category,
      study: { count: studyTally.count, undetermined: studyTally.undetermined, perKm2: studyTally.count / studyKm2 },
      controls: {
        count: controlCount, undetermined: sum(cell, 'undetermined'), perKm2: controlCount / controlsKm2,
        byAoi: controls.map((control) => {
          const tally = cell.byAoi.get(control.id) || blank();
          return { id: control.id, label: control.label, count: tally.count, undetermined: tally.undetermined, perKm2: tally.count / (control.areaM2 / 1e6) };
        }),
      },
      ...statistics(studyTally.count, controlCount, studyKm2, controlsKm2),
    };
  });
  const totalStudy = rows.reduce((total, row) => total + row.study.count, 0);
  const totalControls = rows.reduce((total, row) => total + row.controls.count, 0);
  const comparisons = rows.filter((row) => row.status === 'COMPARED').length;
  return {
    label: NOT_A_FINDING,
    aois: [study, ...controls],
    areas: { studyKm2, controlsKm2 },
    rows,
    total: { study: { count: totalStudy, perKm2: totalStudy / studyKm2 }, controls: { count: totalControls, perKm2: totalControls / controlsKm2 } },
    outside,
    comparisons,
    multiplicity: comparisons
      ? `${comparisons} comparison${comparisons === 1 ? ' was' : 's were'} tested; p-values are not adjusted for multiple comparisons.`
      : `No comparison reached the minimum of ${MIN_COMBINED_RECORDS} combined records.`,
  };
}

function plain(value) {
  if (value === Infinity) return 'infinite (no control records)';
  return value;
}

// A JSON-safe record of what was compared, how, and over which store.
export function comparisonReceipt({ result, store, generatedAt, spatialContract = SPATIAL_CONTRACT }) {
  const study = result.aois[0];
  return {
    contract: COMPARISON_CONTRACT,
    spatial_contract: spatialContract,
    generated_at: generatedAt,
    certification: 'NOT_CERTIFIED',
    label: NOT_A_FINDING,
    store: describeStore(store),
    aois: result.aois.map((item) => ({
      id: item.id, label: item.label, role: item === study ? 'study' : 'control', kind: item.kind, source: item.source,
      area_m2: item.areaM2, area_method: item.areaMethod,
    })),
    areas_km2: { study: result.areas.studyKm2, controls: result.areas.controlsKm2 },
    method: {
      membership: 'Only OBSERVED_POINT and INTERPRETED_POINT records are placed by their declared position; REPRESENTATIVE_POINT '
        + 'stand-ins inside an AOI are counted separately as membership not determined. Nothing is geocoded.',
      density: 'records per km² of AOI area; controls are pooled by summing counts and areas',
      test: 'exact conditional binomial test (two-sided, minimum likelihood) of the study share against its share of the combined area; '
        + 'Clopper-Pearson 95% interval transformed to a rate ratio',
      minimum_combined_records: MIN_COMBINED_RECORDS,
      multiplicity: result.multiplicity,
      synthetic_records: 'excluded',
    },
    comparisons: result.comparisons,
    outside_every_aoi: result.outside,
    rows: result.rows.map((row) => ({
      producer: row.producer, stream: row.stream, category: row.category,
      study_count: row.study.count, study_membership_not_determined: row.study.undetermined, study_per_km2: row.study.perKm2,
      control_count: row.controls.count, control_membership_not_determined: row.controls.undetermined, control_per_km2: row.controls.perKm2,
      status: row.status, ratio: plain(row.ratio), ci_low: row.ci ? plain(row.ci[0]) : null, ci_high: row.ci ? plain(row.ci[1]) : null,
      p_exact: row.p,
    })),
  };
}
