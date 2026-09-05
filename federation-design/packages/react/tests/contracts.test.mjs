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
const gisCss = readFileSync(join(designRoot, 'styles', 'gis.css'), 'utf8')
const snapshot = JSON.parse(readFileSync(join(pkgRoot, 'api-snapshot.json'), 'utf8'))

test('API snapshot is additive over the complete v0.3 public API', () => {
  for (const name of [
    'FEDERATION_STATUS_ROLES', 'FederationThemeProvider', 'useFederationTheme',
    'FederationButton', 'FederationPanel', 'federationStatusRole', 'federationTone',
    'FederationStatusBadge', 'FederationEmptyState', 'FederationStatCard',
  ]) {
    assert.ok(snapshot.exports.includes(name), `${name} missing from snapshot`)
  }
  assert.deepEqual(snapshot.removedExports, [])
})

test('v0.3 status-badge behavior and style hooks remain the default', () => {
  assert.match(indexSource, /FederationStatusBadge\(\{ status, kind = 'presentation'/)
  assert.match(indexSource, /className=\{cx\('fd-status', 'fd-badge'/)
  assert.match(indexSource, /data-status=\{tone\}/)
  assert.match(css, /data-status="critical"/)
})

test('v0.3 empty-state inline descendant rules remain available', () => {
  assert.match(css, /\.fd-empty-state__icon>svg/)
  assert.match(css, /\.fd-empty-state--inline \.fd-empty-state__description/)
  assert.match(css, /\.fd-empty-state--inline \.fd-empty-state__icon\{display:none\}/)
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

test('GIS public API and styling are governed by the package contract', () => {
  for (const name of [
    'createDatasetMapBridge', 'FederationDatasetGrid', 'FederationExportMenu',
    'FederationBasemapSelector', 'FederationMapWorkspace', 'FederationDatasetWorkspace',
  ]) {
    assert.ok(snapshot.exports.includes(name), `${name} missing from snapshot`)
  }
  assert.doesNotMatch(gisCss, /Arial|#[0-9a-f]{3,8}/i)
  assert.match(gisCss, /var\(--fd-font-sans\)/)
  assert.match(gisCss, /var\(--fd-surface\)/)
})
