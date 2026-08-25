import { coerceContradictions, readExplicitState, uniqueNonEmpty } from './intelligenceWorkspaceState';

function firstValue(row, keys) {
  for (const key of keys) {
    const value = row?.[key];
    if (value !== undefined && value !== null && value !== '') return value;
  }
  return undefined;
}

function finiteNumber(value) {
  const number = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(number) ? number : null;
}

function explicitProvenanceState(row) {
  const value = firstValue(row, ['provenance_state', 'provenance_status']);
  return value ? String(value).trim().toLowerCase().replace(/[\s-]+/g, '_') : 'missing';
}

function explicitFreshnessState(row) {
  const value = firstValue(row, ['freshness_state', 'freshness_status']);
  return value ? String(value).trim().toLowerCase().replace(/[\s-]+/g, '_') : 'unknown';
}

function sourcesFromRow(row) {
  const provenanceSource = row?.provenance && typeof row.provenance === 'object' ? row.provenance.source : undefined;
  return uniqueNonEmpty([row?._producers || [], row?.source_id, row?.source, provenanceSource]);
}

function forensicAxes(row) {
  return {
    identity: readExplicitState(row, ['identity_state', 'identity_status', 'identity_class'], 'UNRESOLVED'),
    certification: readExplicitState(row, ['certification_state', 'certification_status'], 'OPEN'),
    epistemic: readExplicitState(row, ['epistemic_class', 'epistemic_state'], 'UNKNOWN'),
    provenance: explicitProvenanceState(row),
    freshness: explicitFreshnessState(row),
  };
}

const common = {
  getId: (row) => String(row?.id ?? ''),
  getConfidence: (row) => firstValue(row, ['confidence']),
  getSignificance: (row) => firstValue(row, ['significance', 'severity', 'priority']),
  getSources: sourcesFromRow,
  getContradictions: coerceContradictions,
  getForensicAxes: forensicAxes,
  getLatitude: (row) => finiteNumber(row?.latitude),
  getLongitude: (row) => finiteNumber(row?.longitude),
};

export const INTELLIGENCE_ADAPTERS = Object.freeze({
  spiderweb: {
    ...common,
    key: 'spiderweb',
    label: 'Spiderweb',
    primaryEntity: 'GraphNodes',
    relatedEntity: 'GraphEdges',
    primaryNoun: 'nodes',
    relatedNoun: 'graph edges',
    temporalPolicy: 'retain-undated',
    temporalNote: 'Graph nodes have no authoritative event-time field in the current Hub contract. Bounded time windows retain undated nodes rather than silently deleting spatial context.',
    getId: (row) => String(row?.node_id ?? row?.id ?? ''),
    getTitle: (row) => row?.label || row?.node_id || 'Untitled node',
    getCategory: (row) => row?.node_type || 'Unknown',
    getLocation: (row) => row?.municipality || 'Location not recorded',
    getSummary: (row) => row?.summary || '',
    getTimestamp: () => null,
    getSearchValues: (row) => [row?.label, row?.node_id, row?.node_type, row?.municipality, row?.summary],
    getRelated: (rows, selected) => rows.filter((row) => row?.source_node_id === selected?.node_id || row?.target_node_id === selected?.node_id),
    getRelatedTitle: (row) => `${row?.source_node_id || '—'} → ${row?.target_node_id || '—'}`,
    getRelatedSubtitle: (row) => [row?.relationship_type, row?.evidence_tier, row?.status].filter(Boolean).join(' · '),
    relatedDisclaimer: 'Graph edges are relationship records. They do not establish canonical identity unless an independent identity adjudication says so.',
    inspectorFields: [
      ['Type', (row) => row?.node_type],
      ['Municipality', (row) => row?.municipality],
      ['Sensitivity', (row) => row?.sensitivity],
    ],
  },
  skywatcher: {
    ...common,
    key: 'skywatcher',
    label: 'Skywatcher',
    primaryEntity: 'AirspaceEvents',
    relatedEntity: 'CorrelationReviews',
    primaryNoun: 'airspace events',
    relatedNoun: 'correlation reviews',
    temporalPolicy: 'exclude-undated',
    temporalNote: 'Bounded time windows require an explicit event_date. Undated airspace events are counted and excluded from bounded windows.',
    getId: (row) => String(row?.event_id ?? row?.id ?? ''),
    getTitle: (row) => row?.title || row?.event_id || 'Untitled airspace event',
    getCategory: (row) => row?.event_type || 'Unknown',
    getLocation: (row) => [row?.municipality, row?.region].filter(Boolean).join(' · ') || 'Location not recorded',
    getSummary: (row) => row?.summary || '',
    getTimestamp: (row) => row?.event_date,
    getSearchValues: (row) => [row?.title, row?.event_id, row?.event_type, row?.municipality, row?.region, row?.source_id, row?.summary],
    getRelated: (rows, selected) => rows.filter((row) => row?.airspace_event_id === selected?.event_id),
    getRelatedTitle: (row) => row?.review_id || 'Correlation review',
    getRelatedSubtitle: (row) => [row?.correlation_type, row?.status, row?.confidence].filter(Boolean).join(' · '),
    relatedDisclaimer: 'Correlation reviews remain correlation evidence. Temporal, spatial, source, or proximity matches are not canonical identity proof.',
    inspectorFields: [
      ['Type', (row) => row?.event_type],
      ['Event date', (row) => row?.event_date],
      ['Date precision', (row) => row?.date_precision],
      ['Source ID', (row) => row?.source_id],
      ['Status', (row) => row?.status],
    ],
  },
  aguayluz: {
    ...common,
    key: 'aguayluz',
    label: 'AguaYLuz',
    primaryEntity: 'InfrastructureAssets',
    relatedEntity: 'ContinuityRisks',
    primaryNoun: 'infrastructure assets',
    relatedNoun: 'continuity risks',
    temporalPolicy: 'retain-undated',
    temporalNote: 'Infrastructure assets are persistent objects in the current Hub contract. Bounded time windows retain undated assets rather than treating missing event time as absence.',
    getId: (row) => String(row?.asset_id ?? row?.id ?? ''),
    getTitle: (row) => row?.name || row?.asset_id || 'Unnamed infrastructure asset',
    getCategory: (row) => row?.asset_type || 'Unknown',
    getLocation: (row) => [row?.municipality, row?.region].filter(Boolean).join(' · ') || 'Location not recorded',
    getSummary: (row) => row?.summary || '',
    getTimestamp: () => null,
    getSearchValues: (row) => [row?.name, row?.asset_id, row?.asset_type, row?.municipality, row?.region, row?.operator, row?.owner_agency, row?.summary],
    getRelated: (rows, selected) => rows.filter((row) => row?.asset_id === selected?.asset_id),
    getRelatedTitle: (row) => row?.risk_id || 'Continuity risk',
    getRelatedSubtitle: (row) => [row?.risk_type, row?.severity, row?.status].filter(Boolean).join(' · '),
    relatedDisclaimer: 'Continuity-risk adjacency or dependency records do not merge asset identity. Source manifestations remain separate unless independently bound.',
    inspectorFields: [
      ['Type', (row) => row?.asset_type],
      ['Municipality', (row) => row?.municipality],
      ['Operator', (row) => row?.operator],
      ['Owner agency', (row) => row?.owner_agency],
      ['Status', (row) => row?.status],
    ],
  },
});

export function getIntelligenceAdapter(key) {
  const adapter = INTELLIGENCE_ADAPTERS[key];
  if (!adapter) throw new Error(`Unknown intelligence adapter: ${key}`);
  return adapter;
}
