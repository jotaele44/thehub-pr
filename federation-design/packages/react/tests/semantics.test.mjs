import test from 'node:test'
import assert from 'node:assert/strict'
import {
  federationStatusRole,
  resolveFederationSemantic,
  FEDERATION_EVIDENCE_TIERS,
  FEDERATION_ASYNC_STATES,
  FEDERATION_EPISTEMIC_STATES,
  FEDERATION_CERTIFICATION_STATES,
} from '../src/semantics.js'

test('legacy status aliases remain backward compatible', () => {
  assert.equal(federationStatusRole('operational'), 'success')
  assert.equal(federationStatusRole('analysis'), 'process')
  assert.equal(federationStatusRole('warning'), 'warning')
  assert.equal(federationStatusRole('danger'), 'danger')
  assert.equal(federationStatusRole('unexpected'), 'neutral')
})

test('semantic axes do not collapse into presentation colors', () => {
  const workflow = resolveFederationSemantic('workflow', 'needs-review')
  assert.deepEqual(workflow, { kind: 'workflow', value: 'needs_review', label: 'Needs review', tone: 'warning' })
  const provenance = resolveFederationSemantic('provenance', 'hash mismatch')
  assert.equal(provenance.value, 'hash_mismatch')
  assert.equal(provenance.tone, 'danger')
})

test('evidence tiers normalize case and preserve the T1-T4 contract', () => {
  assert.deepEqual(FEDERATION_EVIDENCE_TIERS.slice(0, 4), ['T1', 'T2', 'T3', 'T4'])
  assert.equal(resolveFederationSemantic('evidenceTier', 't3').value, 'T3')
})

test('epistemic axis is explicit and unknown values fail to UNKNOWN', () => {
  assert.deepEqual(FEDERATION_EPISTEMIC_STATES, [
    'fact', 'computed', 'binding', 'inference', 'assumption', 'hypothesis', 'unknown',
  ])
  assert.equal(resolveFederationSemantic('epistemic', 'FACT').value, 'fact')
  assert.equal(resolveFederationSemantic('epistemic', 'computed').value, 'computed')
  assert.equal(resolveFederationSemantic('epistemic', 'unrecognized').value, 'unknown')
})

test('certification axis preserves candidate-not-identity and fails unknown values open', () => {
  assert.deepEqual(FEDERATION_CERTIFICATION_STATES, [
    'pass', 'fail', 'open', 'blocked', 'provisional', 'audit_only', 'noncanonical',
    'candidate_not_identity', 'unresolved', 'superseded',
  ])
  const candidate = resolveFederationSemantic('certification', 'CANDIDATE_NOT_IDENTITY')
  assert.equal(candidate.value, 'candidate_not_identity')
  assert.equal(candidate.label, 'Candidate — not identity')
  assert.equal(resolveFederationSemantic('certification', 'mystery').value, 'open')
})

test('invalid values resolve to explicit safe fallbacks', () => {
  assert.equal(resolveFederationSemantic('confidence', 'certain').value, 'unknown')
  assert.equal(resolveFederationSemantic('evidenceTier', 'T9').value, 'ungraded')
  assert.ok(FEDERATION_ASYNC_STATES.includes('offline'))
})

test('unknown semantic kinds fail closed', () => {
  assert.throws(() => resolveFederationSemantic('color', 'red'), /Unknown federation semantic kind/)
})
