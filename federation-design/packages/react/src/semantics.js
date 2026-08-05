export const FEDERATION_PRESENTATION_TONES = Object.freeze([
  'danger', 'success', 'warning', 'info', 'neutral', 'process', 'tier', 'caution', 'elevated',
])

export const FEDERATION_OPERATIONAL_STATES = Object.freeze([
  'operational', 'degraded', 'critical', 'offline', 'unknown',
])

export const FEDERATION_WORKFLOW_STATES = Object.freeze([
  'queued', 'active', 'blocked', 'needs_review', 'complete', 'superseded', 'failed',
])

export const FEDERATION_EVIDENCE_TIERS = Object.freeze(['T1', 'T2', 'T3', 'T4', 'ungraded'])
export const FEDERATION_CONFIDENCE_LEVELS = Object.freeze(['high', 'medium', 'low', 'unknown'])
export const FEDERATION_PROVENANCE_STATES = Object.freeze(['captured', 'verified', 'superseded', 'missing', 'hash_mismatch'])
export const FEDERATION_FRESHNESS_STATES = Object.freeze(['current', 'aging', 'stale', 'unknown'])
export const FEDERATION_ASYNC_STATES = Object.freeze([
  'idle', 'loading', 'empty', 'filtered_empty', 'error', 'partial', 'offline', 'degraded', 'stale',
])

const DEFINITIONS = Object.freeze({
  operational: Object.freeze({
    operational: { label: 'Operational', tone: 'success' },
    degraded: { label: 'Degraded', tone: 'warning' },
    critical: { label: 'Critical', tone: 'danger' },
    offline: { label: 'Offline', tone: 'neutral' },
    unknown: { label: 'Unknown', tone: 'neutral' },
  }),
  workflow: Object.freeze({
    queued: { label: 'Queued', tone: 'neutral' },
    active: { label: 'Active', tone: 'process' },
    blocked: { label: 'Blocked', tone: 'danger' },
    needs_review: { label: 'Needs review', tone: 'warning' },
    complete: { label: 'Complete', tone: 'success' },
    superseded: { label: 'Superseded', tone: 'info' },
    failed: { label: 'Failed', tone: 'danger' },
  }),
  evidenceTier: Object.freeze({
    T1: { label: 'T1 · Technical', tone: 'tier' },
    T2: { label: 'T2 · Operational', tone: 'tier' },
    T3: { label: 'T3 · Eyewitness', tone: 'tier' },
    T4: { label: 'T4 · Secondary', tone: 'tier' },
    ungraded: { label: 'Ungraded', tone: 'neutral' },
  }),
  confidence: Object.freeze({
    high: { label: 'High confidence', tone: 'success' },
    medium: { label: 'Medium confidence', tone: 'warning' },
    low: { label: 'Low confidence', tone: 'elevated' },
    unknown: { label: 'Unknown confidence', tone: 'neutral' },
  }),
  provenance: Object.freeze({
    captured: { label: 'Captured', tone: 'info' },
    verified: { label: 'Verified', tone: 'success' },
    superseded: { label: 'Superseded', tone: 'neutral' },
    missing: { label: 'Missing provenance', tone: 'warning' },
    hash_mismatch: { label: 'Hash mismatch', tone: 'danger' },
  }),
  freshness: Object.freeze({
    current: { label: 'Current', tone: 'success' },
    aging: { label: 'Aging', tone: 'caution' },
    stale: { label: 'Stale', tone: 'warning' },
    unknown: { label: 'Unknown freshness', tone: 'neutral' },
  }),
  asyncState: Object.freeze({
    idle: { label: 'Idle', tone: 'neutral' },
    loading: { label: 'Loading', tone: 'process' },
    empty: { label: 'No records', tone: 'neutral' },
    filtered_empty: { label: 'No matching records', tone: 'info' },
    error: { label: 'Unable to load', tone: 'danger' },
    partial: { label: 'Partial data', tone: 'warning' },
    offline: { label: 'Offline', tone: 'neutral' },
    degraded: { label: 'Degraded', tone: 'warning' },
    stale: { label: 'Stale data', tone: 'caution' },
  }),
})

const FALLBACKS = Object.freeze({
  operational: 'unknown', workflow: 'queued', evidenceTier: 'ungraded', confidence: 'unknown',
  provenance: 'missing', freshness: 'unknown', asyncState: 'idle',
})

const LEGACY_TONE_ALIASES = Object.freeze({
  operational: 'success', degraded: 'warning', critical: 'danger', offline: 'neutral',
  information: 'info', analysis: 'process',
})

function normalizeValue(kind, value) {
  const raw = String(value ?? '').trim()
  if (kind === 'evidenceTier' && /^t[1-4]$/i.test(raw)) return raw.toUpperCase()
  return raw.toLowerCase().replace(/[\s-]+/g, '_')
}

export function resolveFederationSemantic(kind, value) {
  const definitions = DEFINITIONS[kind]
  if (!definitions) throw new Error(`Unknown federation semantic kind: ${kind}`)
  const normalized = normalizeValue(kind, value)
  const resolvedValue = definitions[normalized] ? normalized : FALLBACKS[kind]
  return Object.freeze({ kind, value: resolvedValue, ...definitions[resolvedValue] })
}

export function federationStatusRole(status) {
  const normalized = String(status ?? 'neutral').trim().toLowerCase().replace(/[\s-]+/g, '_')
  if (FEDERATION_PRESENTATION_TONES.includes(normalized)) return normalized
  return LEGACY_TONE_ALIASES[normalized] || 'neutral'
}

export function federationTone(status) {
  const tone = federationStatusRole(status)
  return { className: 'fd-status', 'data-status': tone, 'data-tone': tone }
}

export const FEDERATION_SEMANTIC_DEFINITIONS = DEFINITIONS
