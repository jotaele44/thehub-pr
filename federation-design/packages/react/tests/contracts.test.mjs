import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const pkgRoot = join(here, '..')
const designRoot = join(pkgRoot, '..', '..')
const indexSource = readFileSync(join(pkgRoot, 'src', 'index.jsx'), 'utf8')
const css = ['foundation.css', 'primitives.css', 'states.css'].map((name) => readFileSync(join(designRoot, 'styles', name), 'utf8')).join('\n')
const snapshot = JSON.parse(readFileSync(join(pkgRoot, 'api-snapshot.json'), 'utf8'))

test('API snapshot is additive over the v0.3 primitives', () => {
  for (const name of ['FederationButton', 'FederationPanel', 'FederationStatusBadge', 'FederationEmptyState', 'FederationStatCard']) {
    assert.ok(snapshot.exports.includes(name), `${name} missing from snapshot`)
  }
  assert.deepEqual(snapshot.removedExports, [])
})

test('async-state family encodes live regions and failure alerts', () => {
  assert.match(indexSource, /role=\{role\}/)
  assert.match(indexSource, /aria-live=\{live\}/)
  assert.match(indexSource, /aria-busy=\{busy \|\| undefined\}/)
  assert.match(indexSource, /semantic\.value === 'error' \? 'alert'/)
})

test('icon buttons require an accessible name', () => {
  assert.match(indexSource, /requires label or aria-label/)
  assert.match(indexSource, /aria-label=\{accessibleName\}/)
})

test('CSS preserves reduced motion and forced-colors behavior', () => {
  assert.match(css, /prefers-reduced-motion: reduce/)
  assert.match(css, /forced-colors: active/)
  assert.match(css, /scroll-behavior:auto!important/)
})
