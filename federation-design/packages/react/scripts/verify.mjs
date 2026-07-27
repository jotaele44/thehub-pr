import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const pkgRoot = join(here, '..')
const designRoot = join(pkgRoot, '..', '..')
const readJson = (path) => JSON.parse(readFileSync(path, 'utf8'))
const pkg = readJson(join(pkgRoot, 'package.json'))
const snapshot = readJson(join(pkgRoot, 'api-snapshot.json'))
const tokens = readJson(join(designRoot, 'tokens', 'federation.tokens.json'))
const schema = readJson(join(designRoot, 'tokens', 'federation.tokens.schema.json'))
const harness = readJson(join(designRoot, 'test-harness', 'test-harness.contract.json'))
const indexSource = readFileSync(join(pkgRoot, 'src', 'index.jsx'), 'utf8')
const semanticsSource = readFileSync(join(pkgRoot, 'src', 'semantics.js'), 'utf8')
const css = ['foundation.css', 'primitives.css', 'states.css'].map((name) => readFileSync(join(designRoot, 'styles', name), 'utf8')).join('\n')

function fail(message) { console.error(`[verify] ${message}`); process.exitCode = 1 }
function requireCondition(condition, message) { if (!condition) fail(message) }

requireCondition(pkg.version === snapshot.packageVersion, 'package version and API snapshot version differ')
requireCondition(tokens.version === '2.0.0', 'token version must be 2.0.0')
requireCondition(schema.properties?.version?.const === tokens.version, 'token schema version does not match token source')
requireCondition(Array.isArray(snapshot.exports) && snapshot.exports.length >= 30, 'API snapshot is unexpectedly small')
requireCondition(harness.viewports.length === 6, 'test harness must define six certified viewports')
requireCondition(harness.states.includes('offline') && harness.states.includes('filtered_empty'), 'test harness state matrix is incomplete')

for (const symbol of snapshot.exports) {
  requireCondition(indexSource.includes(symbol) || semanticsSource.includes(symbol), `API snapshot symbol missing from source: ${symbol}`)
}

for (const fragment of ['role={role}', 'aria-live={live}', 'aria-busy={busy || undefined}', 'requires label or aria-label']) {
  requireCondition(indexSource.includes(fragment), `accessibility contract missing: ${fragment}`)
}
for (const fragment of ['prefers-reduced-motion: reduce', 'animation-duration:.01ms!important', 'transition-duration:.01ms!important', 'scroll-behavior:auto!important']) {
  requireCondition(css.includes(fragment), `reduced-motion contract missing: ${fragment}`)
}
for (const className of ['.fd-button', '.fd-icon-button', '.fd-badge', '.fd-source-badge', '.fd-state', '.fd-stat-card']) {
  requireCondition(css.includes(className), `required CSS primitive missing: ${className}`)
}

function rgb(hex) {
  const value = Number.parseInt(hex.slice(1), 16)
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255]
}
function luminance(hex) {
  const channel = rgb(hex).map((v) => {
    const s = v / 255
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * channel[0] + 0.7152 * channel[1] + 0.0722 * channel[2]
}
function contrast(a, b) {
  const [lighter, darker] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (lighter + 0.05) / (darker + 0.05)
}

for (const [themeName, surface] of Object.entries({ light: tokens.semantic.light, dark: tokens.semantic.dark })) {
  for (const textKey of ['textPrimary', 'textSecondary']) {
    const ratio = contrast(surface[textKey], surface.background)
    requireCondition(ratio >= 4.5, `${themeName}.${textKey} contrast ${ratio.toFixed(2)} is below 4.5`) 
  }
}
for (const [name, token] of Object.entries(tokens.semantic.statusRoles)) {
  const light = contrast(token.foreground, token.background)
  const dark = contrast(token.foregroundDark, token.backgroundDark)
  requireCondition(light >= 4.5, `statusRoles.${name} light contrast ${light.toFixed(2)} is below 4.5`)
  requireCondition(dark >= 4.5, `statusRoles.${name} dark contrast ${dark.toFixed(2)} is below 4.5`)
}
for (const groupName of ['operational', 'workflow', 'evidenceTier', 'confidence', 'provenance', 'freshness', 'asyncState']) {
  for (const [name, mapping] of Object.entries(tokens.semantic[groupName])) {
    requireCondition(Boolean(tokens.semantic.statusRoles[mapping.tone]), `${groupName}.${name} references unknown tone ${mapping.tone}`)
  }
}

if (!process.exitCode) console.log(`[verify] ${snapshot.exports.length} exports; tokens, a11y, contrast, reduced motion and harness contracts valid`)
