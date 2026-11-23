import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { BUNDLED_STYLES, designRoot, readBundledCss, stylePath } from '../scripts/sources.mjs'
import { FEDERATION_SHELL_BREAKPOINTS } from '../src/shell/nav.js'

const tokens = JSON.parse(readFileSync(join(designRoot, 'tokens', 'federation.tokens.json'), 'utf8'))
const raw = readFileSync(stylePath('shell.css'), 'utf8')
const css = raw.replace(/\/\*[\s\S]*?\*\//g, '')
const kebab = (name) => name.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`)
const declared = (property) => css.match(new RegExp(`${property}:\\s*([^;]+);`))?.[1].trim()

test('shell.css ships in the bundled stylesheet and the canonical import list', () => {
  assert.ok(BUNDLED_STYLES.includes('shell.css'))
  assert.match(readFileSync(stylePath('federation.css'), 'utf8'), /@import "\.\/shell\.css";/)
})

test('layout, layering and breakpoint properties equal their tokens', () => {
  for (const [group, prefix] of [['layout', 'layout'], ['layering', 'layer'], ['breakpoints', 'breakpoint']]) {
    for (const [name, value] of Object.entries(tokens[group])) {
      assert.equal(declared(`--fd-${prefix}-${kebab(name)}`), String(value), `--fd-${prefix}-${kebab(name)}`)
    }
  }
})

test('every repository accent is addressable by name and equals its token', () => {
  for (const [repo, value] of Object.entries(tokens.repoAccents)) {
    assert.equal(declared(`--fd-repo-accent-${repo}`), value, repo)
  }
  const foundation = readFileSync(stylePath('foundation.css'), 'utf8')
  for (const [repo, value] of Object.entries(tokens.repoAccents)) {
    assert.ok(foundation.includes(`[data-repo="${repo}"]{--fd-accent:${value}}`), `${repo} accent differs from foundation.css`)
  }
})

test('the font stack leads with the family the applications actually load', () => {
  const foundation = readFileSync(stylePath('foundation.css'), 'utf8')
  const stack = foundation.match(/--fd-font-sans:\s*([^;]+);/)[1]
  // @fontsource-variable/inter registers "Inter Variable", not "Inter". With
  // only "Inter" in the stack every application rendered a system fallback.
  assert.match(stack, /^"Inter Variable", Inter,/)
  assert.match(tokens.typography.fontFamily, /^Inter Variable, Inter,/)
})

test('media queries use only the two token breakpoints the shell supports', () => {
  const widths = [...css.matchAll(/@media\s*\((?:max|min)-width:\s*([\d.]+)px\)/g)].map((match) => Number(match[1]))
  assert.ok(widths.length >= 2)
  const allowed = Object.values(FEDERATION_SHELL_BREAKPOINTS).flatMap((value) => [value, value - 0.02])
  for (const width of widths) assert.ok(allowed.includes(width), `unexpected breakpoint ${width}px`)
  assert.equal(`${FEDERATION_SHELL_BREAKPOINTS.tablet}px`, tokens.breakpoints.tablet)
  assert.equal(`${FEDERATION_SHELL_BREAKPOINTS.desktop}px`, tokens.breakpoints.desktop)
})

test('the two mobile-below blocks are identical apart from the breakpoint they name', () => {
  const block = (width, name) => {
    const start = css.indexOf(`@media (max-width: ${width}px)`)
    assert.ok(start >= 0, `missing block for ${name}`)
    const end = css.indexOf('\n}', start)
    return css.slice(css.indexOf('{', start) + 1, end).replaceAll(`data-mobile-below="${name}"`, 'data-mobile-below="X"')
  }
  const tablet = block('767.98', 'tablet')
  assert.equal(tablet, block('1279.98', 'desktop'))
  assert.match(tablet, /\.fd-shell__nav \{ display: none; \}/)
  assert.match(tablet, /\.fd-shell__mobile-nav \{ display: block; \}/)
  assert.match(tablet, /safe-area-inset-bottom/)
})

// Split a stylesheet into top-level rule selectors, descending into @media.
function selectors(source) {
  const out = []
  let depth = 0
  let buffer = ''
  for (const char of source) {
    if (char === '{') {
      const head = buffer.trim()
      if (head.startsWith('@')) { depth = 0 } else if (depth === 0) { out.push(head) }
      if (!head.startsWith('@')) depth += 1
      buffer = ''
    } else if (char === '}') {
      depth = Math.max(0, depth - 1)
      buffer = ''
    } else if (depth === 0) {
      buffer += char
    }
  }
  return out
}

// The selectors in a list, split on top-level commas only: the commas inside
// :where(a, b) or :is(a, b) belong to one selector.
function selectorList(selector) {
  const parts = []
  let depth = 0
  let current = ''
  for (const char of selector) {
    if (char === '(') depth += 1
    if (char === ')') depth -= 1
    if (char === ',' && depth === 0) {
      parts.push(current.trim())
      current = ''
    } else {
      current += char
    }
  }
  parts.push(current.trim())
  return parts
}

test('every rule is scoped to the shell, so the stylesheet is inert until used', () => {
  const found = selectors(css)
  assert.ok(found.length > 40, `parsed only ${found.length} rules`)
  const globals = found.filter((selector) => !selectorList(selector).every((part) => part.startsWith('.fd-')))
  assert.deepEqual(globals.map((selector) => selector.replace(/\s+/g, ' ')), [':root', ':root, [data-theme], [data-repo]'])
  assert.deepEqual(selectorList('.a :where(b, c), .d'), ['.a :where(b, c)', '.d'])
  // The two global rules may declare custom properties and nothing else.
  for (const selector of [':root {', '[data-repo] {']) {
    const start = css.indexOf(selector)
    const body = css.slice(css.indexOf('{', start) + 1, css.indexOf('}', start))
    for (const declaration of body.split(';').map((value) => value.trim()).filter(Boolean)) {
      assert.match(declaration, /^--fd-[a-z0-9-]+:/, `global rule sets a real property: ${declaration}`)
    }
  }
})

test('touch targets, the current-page marker and forced colours are covered', () => {
  assert.match(css, /\.fd-nav__link \{[^}]*min-height: var\(--fd-touch-min\)/)
  assert.match(css, /\.fd-mobile-nav__link \{[^}]*min-width: var\(--fd-touch-min\)/)
  assert.match(css, /\.fd-mobile-nav__link \{[^}]*min-height: var\(--fd-layout-mobile-nav\)/)
  assert.match(css, /\.fd-nav__link\[aria-current="page"\]/)
  assert.match(css, /@media \(forced-colors: active\)/)
  assert.match(css, /\.fd-inspector:modal/)
  assert.match(css, /\.fd-shell__header :where\(button, a, \[role="button"\]\) \{[^}]*min-height: var\(--fd-touch-min\)/)
  assert.doesNotMatch(css, /:has\(/, 'the shell must not depend on :has()')
})

const channels = (hex) => [1, 3, 5].map((index) => Number.parseInt(hex.slice(index, index + 2), 16))
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

test('--fd-accent-strong is legible on every surface, for every repository and theme', () => {
  const mix = declared('--fd-accent-strong')
  const share = Number(mix.match(/^color-mix\(in srgb, var\(--fd-accent\) (\d+)%, var\(--fd-text\)\)$/)?.[1])
  assert.ok(share > 0 && share < 100, `unexpected definition: ${mix}`)
  let worst = Infinity
  for (const [theme, surface] of Object.entries({ light: tokens.semantic.light, dark: tokens.semantic.dark })) {
    const text = channels(surface.textPrimary)
    for (const [repo, accent] of Object.entries(tokens.repoAccents)) {
      // color-mix in srgb interpolates the gamma-encoded channels.
      const strong = channels(accent).map((value, index) => (value * share + text[index] * (100 - share)) / 100)
      for (const key of ['background', 'surface', 'surfaceSecondary']) {
        const ratio = contrast(strong, channels(surface[key]))
        worst = Math.min(worst, ratio)
        assert.ok(ratio >= 4.5, `${repo} ${theme} on ${key}: ${ratio.toFixed(2)} is below 4.5`)
      }
    }
  }
  assert.ok(worst < 21)
})

test('text on an accent fill and the focus ring use the legible accent roles', () => {
  // Both roles are aliases of values the test above already measures: the
  // strong accent against every surface. That makes the fill/text pair at
  // least 4.5:1 and the ring at least 3:1 for every repository and theme.
  assert.equal(declared('--fd-accent-contrast'), 'var(--fd-surface)')
  assert.equal(declared('--fd-focus-ring'), 'var(--fd-accent-strong)')
  const bundled = readBundledCss()
  assert.match(bundled, /\.fd-button--primary\{background:var\(--fd-accent-strong,var\(--fd-accent\)\);color:var\(--fd-accent-contrast,#fff\)\}/)
  // Outside the definitions and the two fallbacks, nothing draws with the raw accent.
  const uses = [...bundled.matchAll(/[^{};]*var\(--fd-accent\)[^;}]*/g)].map((match) => match[0].trim())
  for (const use of uses) {
    assert.match(use, /^--fd-accent-strong:|var\(--fd-(?:accent-strong|focus-ring), ?var\(--fd-accent\)\)/, `raw accent used directly: ${use}`)
  }
  assert.doesNotMatch(bundled, /outline:[^;}]*solid var\(--fd-accent\)/)
})

test('the raw accent is never used where the strong accent is required', () => {
  assert.doesNotMatch(css.replace(/--fd-accent-strong:[^;]+;/, ''), /var\(--fd-accent\)/)
})
