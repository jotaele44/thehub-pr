import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { BUNDLED_STYLES, SEPARATE_STYLES, designRoot, pkgRoot, stylePath } from '../scripts/sources.mjs'

const strip = (source) => source.replace(/\/\*[\s\S]*?\*\//g, '')
const bridge = strip(readFileSync(stylePath('shadcn-bridge.css'), 'utf8'))
const foundation = strip(readFileSync(stylePath('foundation.css'), 'utf8'))
const shell = strip(readFileSync(stylePath('shell.css'), 'utf8'))
const tokens = JSON.parse(readFileSync(join(designRoot, 'tokens', 'federation.tokens.json'), 'utf8'))
const pkg = JSON.parse(readFileSync(join(pkgRoot, 'package.json'), 'utf8'))

const declarations = (source) => Object.fromEntries([...source.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/g)].map((match) => [match[1], match[2].trim()]))
const block = (source, selector) => {
  const start = source.indexOf(selector)
  assert.ok(start >= 0, `missing rule: ${selector}`)
  return source.slice(source.indexOf('{', start) + 1, source.indexOf('}', start))
}
const bridged = declarations(bridge)

// Every shadcn colour and shape variable used by the six JSX applications.
const CORE = ['background', 'foreground', 'card', 'card-foreground', 'popover', 'popover-foreground', 'primary', 'primary-foreground', 'secondary', 'secondary-foreground', 'muted', 'muted-foreground', 'accent', 'accent-foreground', 'destructive', 'destructive-foreground', 'border', 'input', 'ring', 'radius']
const CHART = [1, 2, 3, 4, 5].map((index) => `chart-${index}`)
const SIDEBAR = ['background', 'foreground', 'primary', 'primary-foreground', 'accent', 'accent-foreground', 'border', 'ring'].map((name) => `sidebar-${name}`)

test('the bridge defines the complete shadcn variable set, and only that', () => {
  assert.deepEqual(Object.keys(bridged).sort(), [...CORE, ...CHART, ...SIDEBAR].map((name) => `--${name}`).sort())
})

test('every value is a federation token or a mix of tokens, never a literal colour', () => {
  for (const [name, value] of Object.entries(bridged)) {
    assert.match(value, /^(var\(--fd-[a-z0-9-]+\)|color-mix\(in srgb, var\(--fd-[a-z0-9-]+\) \d+%, var\(--fd-[a-z0-9-]+\)\))$/, `${name}: ${value}`)
  }
  assert.doesNotMatch(bridge, /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(|\boklch\(/)
  assert.doesNotMatch(bridge, /--font-/, 'fonts are deliberately not bridged')
})

test('it is opt-in: a separate export, re-declared wherever theme or accent can change', () => {
  assert.ok(SEPARATE_STYLES.includes('shadcn-bridge.css'))
  assert.ok(!BUNDLED_STYLES.includes('shadcn-bridge.css'))
  assert.equal(pkg.exports['./shadcn-bridge.css'], './dist/shadcn-bridge.css')
  assert.doesNotMatch(readFileSync(stylePath('federation.css'), 'utf8'), /shadcn-bridge/)
  assert.match(bridge, /:root,\s*\[data-theme\],\s*\[data-repo\]\s*\{/)
  assert.equal((bridge.match(/\{/g) || []).length, 1, 'one rule only')
})

// Resolve a bridged variable to a colour for one theme and one repository.
const light = declarations(block(foundation, ':root {'))
const dark = { ...light, ...declarations(block(foundation, '[data-theme="dark"] {')) }
const strong = declarations(shell)['--fd-accent-strong']
const hex = (value) => [1, 3, 5].map((index) => Number.parseInt(value.slice(index, index + 2), 16))
function resolve(value, scope) {
  const expression = value.trim()
  if (/^#[0-9a-f]{6}$/i.test(expression)) return hex(expression)
  const reference = expression.match(/^var\((--[a-z0-9-]+)\)$/)
  if (reference) {
    const next = scope[reference[1]]
    assert.ok(next !== undefined, `unresolved ${reference[1]}`)
    return resolve(next, scope)
  }
  const mix = expression.match(/^color-mix\(in srgb, (.+?) (\d+)%, (.+)\)$/)
  assert.ok(mix, `cannot resolve: ${expression}`)
  const [a, b, share] = [resolve(mix[1], scope), resolve(mix[3], scope), Number(mix[2])]
  return a.map((channel, index) => (channel * share + b[index] * (100 - share)) / 100)
}
const luminance = (rgb) => {
  const [r, g, b] = rgb.map((value) => {
    const s = value / 255
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
const contrast = (a, b) => {
  const [lighter, darker] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (lighter + 0.05) / (darker + 0.05)
}
function eachScope(callback) {
  for (const [theme, base] of Object.entries({ light, dark })) {
    for (const [repo, accent] of Object.entries(tokens.repoAccents)) {
      const scope = { ...base, '--fd-accent': accent, '--fd-accent-strong': strong, ...bridged }
      callback((name) => resolve(`var(--${name})`, scope), `${repo} ${theme}`)
    }
  }
}

test('the foundation values the test resolves against are the token values', () => {
  assert.equal(light['--fd-bg'], tokens.semantic.light.background)
  assert.equal(dark['--fd-surface'], tokens.semantic.dark.surface)
  assert.equal(dark['--fd-text'], tokens.semantic.dark.textPrimary)
})

test('every text pair meets 4.5:1 for every repository in both themes', () => {
  const pairs = [
    ['foreground', 'background'], ['card-foreground', 'card'], ['popover-foreground', 'popover'],
    ['primary-foreground', 'primary'], ['secondary-foreground', 'secondary'], ['muted-foreground', 'muted'],
    ['muted-foreground', 'background'], ['muted-foreground', 'card'], ['accent-foreground', 'accent'],
    ['destructive-foreground', 'destructive'], ['destructive', 'background'], ['primary', 'background'], ['primary', 'card'],
    ['sidebar-foreground', 'sidebar-background'], ['sidebar-primary-foreground', 'sidebar-primary'],
    ['sidebar-accent-foreground', 'sidebar-accent'], ['sidebar-primary', 'sidebar-background'],
  ]
  let checked = 0
  eachScope((colour, where) => {
    for (const [fg, bg] of pairs) {
      const ratio = contrast(colour(fg), colour(bg))
      assert.ok(ratio >= 4.5, `${where}: ${fg} on ${bg} is ${ratio.toFixed(2)}`)
      checked += 1
    }
  })
  assert.equal(checked, pairs.length * 14)
})

test('chart colours and the focus ring meet 3:1 against the surfaces they sit on', () => {
  eachScope((colour, where) => {
    for (const name of [...CHART, 'ring', 'sidebar-ring']) {
      for (const surface of ['card', 'background']) {
        const ratio = contrast(colour(name), colour(surface))
        assert.ok(ratio >= 3, `${where}: ${name} on ${surface} is ${ratio.toFixed(2)}`)
      }
    }
  })
})
