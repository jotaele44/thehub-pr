// Visual semantics for FEDERATION_EPISTEMIC_STATE_CONTRACT_V1 (schemas/federation/
// epistemic_state.v1.schema.json; Python mirror src/hub/epistemic.py).
//
// Every axis is rendered as "<axis>: <value label>" text. Colour only reinforces
// the text and is never the sole carrier of meaning (INTELLIGENCE_UI_ARCHITECTURE_V1).
// Unknown or missing values fail closed to the axis sentinel.

const TONE = {
  measured: 'bg-status-success/15 text-status-success-fg border-status-success/40',
  computed: 'bg-status-info/15 text-status-info-fg border-status-info/40',
  curated: 'bg-status-warning/15 text-status-warning-fg border-status-warning/40',
  interpretive: 'bg-status-process/15 text-status-process-fg border-status-process/40',
  good: 'bg-status-success/15 text-status-success-fg border-status-success/40',
  caution: 'bg-status-caution/15 text-status-caution-fg border-status-caution/40',
  danger: 'bg-status-danger/15 text-status-danger-fg border-status-danger/40',
  neutral: 'bg-status-neutral/15 text-status-neutral-fg border-status-neutral/40',
};

const v = (label, tone, description) => ({ label, tone, description });

export const EVIDENCE_AXES = Object.freeze([
  {
    key: 'epistemic_class',
    label: 'Class',
    basisKey: 'epistemic_class_basis',
    sentinel: 'UNCLASSIFIED',
    values: {
      MEASURED: v('Measured', TONE.measured, 'Observed by an instrument or provider measurement.'),
      COMPUTED: v('Computed', TONE.computed, 'Derived by software from inputs; reproducible, not observed.'),
      CURATED: v('Curated', TONE.curated, 'Documentary or human-curated record with sources.'),
      INTERPRETIVE: v('Interpretive', TONE.interpretive, 'A model or interpretation; explicitly not a measurement.'),
      UNCLASSIFIED: v('Unclassified', TONE.neutral, 'The producer has not declared how this was known; nothing is assumed.'),
    },
  },
  {
    key: 'data_stage',
    label: 'Stage',
    sentinel: 'UNKNOWN',
    values: {
      RAW: v('Raw', TONE.neutral), NORMALIZED: v('Normalized', TONE.neutral), CANONICAL: v('Canonical', TONE.neutral),
      EVIDENCE_CLASSIFICATION: v('Evidence classification', TONE.neutral), FINDING: v('Finding', TONE.curated),
      COMPUTATION: v('Computation', TONE.computed), INTERPRETATION: v('Interpretation', TONE.interpretive),
      REPORT: v('Report', TONE.neutral), UNKNOWN: v('Unknown', TONE.neutral),
    },
  },
  {
    key: 'identity_state',
    label: 'Identity',
    basisKey: 'identity_basis',
    sentinel: 'UNRESOLVED',
    values: {
      BOUND: v('Bound', TONE.good, 'Identity bound by an adjudicated decision.'),
      CANDIDATE: v('Candidate', TONE.caution, 'Candidate identity; not a decision.'),
      UNRESOLVED: v('Unresolved', TONE.neutral, 'No identity adjudication.'),
      CONFLICTING: v('Conflicting', TONE.danger, 'Contradicting identity assertions exist.'),
    },
  },
  {
    key: 'source_state',
    label: 'Source',
    basisKey: 'source_state_basis',
    sentinel: 'SOURCE_MISSING',
    values: {
      SOURCE_BOUND: v('Bound', TONE.good, 'Source record resolves with a retrievable locator.'),
      SOURCE_REPORTED: v('Reported', TONE.caution, 'A source is cited but the Hub cannot bind it.'),
      SOURCE_MISSING: v('Missing', TONE.danger, 'No source reference.'),
      SOURCE_BLOCKED: v('Blocked', TONE.danger, 'Source exists but is blocked or unavailable.'),
    },
  },
  {
    key: 'temporal_state',
    label: 'Time state',
    basisKey: 'temporal_state_basis',
    sentinel: 'UNKNOWN',
    values: {
      LIVE: v('Live', TONE.good), CURRENT: v('Current', TONE.good), STALE: v('Stale', TONE.danger),
      HISTORICAL: v('Historical', TONE.neutral), UNKNOWN: v('Unknown', TONE.neutral),
    },
  },
  {
    key: 'temporal_precision',
    label: 'Time precision',
    basisKey: 'temporal_basis',
    sentinel: 'UNKNOWN',
    values: {
      EXACT_TIMESTAMP: v('Exact timestamp', TONE.good), BOUNDED_INTERVAL: v('Bounded interval', TONE.caution),
      DATE_ONLY: v('Date only', TONE.neutral), MONTH_YEAR: v('Month/year', TONE.neutral),
      YEAR_ONLY: v('Year only', TONE.neutral), APPROXIMATE: v('Approximate', TONE.caution), UNKNOWN: v('Unknown', TONE.neutral),
    },
  },
  {
    key: 'observation_state',
    label: 'Observation',
    basisKey: 'observation_state_basis',
    sentinel: 'UNKNOWN',
    values: {
      OBSERVED_PRESENT: v('Observed present', TONE.good),
      OBSERVED_ABSENT: v('Observed absent', TONE.caution, 'Absence declared with a coverage basis.'),
      NOT_OBSERVED: v('Not observed', TONE.neutral, 'Not observed is not the same as observed absent.'),
      UNKNOWN: v('Unknown', TONE.neutral),
    },
  },
  {
    key: 'geometry_precision',
    label: 'Geometry',
    basisKey: 'geometry_basis',
    sentinel: 'UNKNOWN',
    values: {
      OBSERVED_POINT: v('Observed point', TONE.good), INTERPRETED_POINT: v('Interpreted point', TONE.caution),
      REPRESENTATIVE_POINT: v('Representative point', TONE.caution, 'A point standing in for an area; not an observed location.'),
      AREA_REFERENCE: v('Area reference', TONE.neutral), UNKNOWN: v('Unknown', TONE.neutral),
    },
  },
]);

export const EDGE_STATES = Object.freeze({
  DOCUMENTED: v('Documented', TONE.good),
  COMPUTED: v('Computed', TONE.computed),
  CANDIDATE: v('Candidate', TONE.caution, 'A discovery signal, not a relationship claim.'),
  CONFLICTING: v('Conflicting', TONE.danger),
  REJECTED: v('Rejected', TONE.neutral),
  UNKNOWN: v('Unknown', TONE.neutral),
});

export const CONTRADICTION_STATES = Object.freeze({
  OPEN: v('Open', TONE.danger), NARROWED: v('Narrowed', TONE.caution), RESOLVED: v('Resolved', TONE.good),
  SUPERSEDED: v('Superseded', TONE.neutral), UNRESOLVABLE: v('Unresolvable', TONE.caution),
});

export const SYNTHETIC_TONE = TONE.danger;

/** The display value for one axis of an Evidence Object; fails closed to the axis sentinel. */
export function axisValue(axis, value) {
  const key = typeof value === 'string' && axis.values[value] ? value : axis.sentinel;
  return { value: key, ...axis.values[key] };
}

export function edgeState(value) {
  const key = typeof value === 'string' && EDGE_STATES[value] ? value : 'UNKNOWN';
  return { value: key, ...EDGE_STATES[key] };
}

export function contradictionState(value) {
  const key = typeof value === 'string' && CONTRADICTION_STATES[value] ? value : 'OPEN';
  return { value: key, ...CONTRADICTION_STATES[key] };
}

/** Deep link to the provenance inspector for a Hub store record. */
export function evidenceHref(collection, recordId) {
  return `/evidence/${encodeURIComponent(collection)}/${encodeURIComponent(recordId)}`;
}

/**
 * The canonical Evidence Object reference for a UI row, or null.
 * Only rows projected from a producer's canonical stream (they carry
 * `_producers`) have one; locally created or seeded rows do not.
 */
export function canonicalEvidenceRef(row) {
  if (!row || !Array.isArray(row._producers) || row._producers.length === 0) return null;
  if (row.observation_id) return { collection: 'Observations', id: String(row.observation_id) };
  if (row.relationship_id) return { collection: 'Relationships', id: String(row.relationship_id) };
  if (row.alert_id) return { collection: 'Alerts', id: String(row.alert_id) };
  if (row.entity_id) return { collection: 'Entities', id: String(row.entity_id) };
  if (row.source_id && 'source_name' in row) return { collection: 'Sources', id: String(row.source_id) };
  return null;
}
