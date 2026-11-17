// Source contracts for the shell components. The package has no JSX
// transform, so components are not rendered here; they are rendered, in three
// browsers, by fixture-lab/tests/runtime-matrix.mjs. These tests pin the
// accessibility and dependency decisions that a refactor must not lose.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { pkgRoot, publicExports } from '../scripts/sources.mjs'

const dir = join(pkgRoot, 'src', 'shell')
const files = Object.fromEntries(readdirSync(dir).sort().map((name) => [name, readFileSync(join(dir, name), 'utf8')]))
const all = Object.values(files).join('\n')
const pkg = JSON.parse(readFileSync(join(pkgRoot, 'package.json'), 'utf8'))

test('the shell exports exactly its documented surface', () => {
  const exported = publicExports()
  for (const name of [
    'FederationAppShell', 'FederationModuleNav', 'FederationMobileNav', 'FederationInspectorPanel', 'FederationStatusBar',
    'defineFederationNav', 'flattenFederationNav', 'matchFederationNavItem',
  ]) assert.ok(exported.has(name), `${name} is not exported`)
  for (const internal of ['NavEntry', 'cx', 'splitMobileNav', 'resolveNavLabel', 'normalizeNavPath']) {
    assert.ok(!exported.has(internal), `${internal} leaked into the public API`)
  }
  assert.equal(pkg.exports['./nav'], './src/shell/nav.js')
})

test('the shell has no dependency beyond React, and knows nothing about routing', () => {
  const imports = [...all.matchAll(/from\s+'([^']+)'/g)].map((match) => match[1])
  for (const source of imports) assert.ok(source === 'react' || source.startsWith('./'), `unexpected import: ${source}`)
  assert.doesNotMatch(all, /react-router|next\/|window\.location|history\.push/)
  assert.doesNotMatch(files['nav.js'], /from\s+'react'|<[A-Za-z]/, 'nav.js must stay free of React and JSX')
  assert.deepEqual(pkg.dependencies, undefined)
})

test('navigation is a labelled landmark with one current page', () => {
  assert.match(files['ModuleNav.jsx'], /<nav aria-label=\{label\}/)
  assert.match(files['ModuleNav.jsx'], /label = 'Primary'/)
  assert.match(files['MobileNav.jsx'], /<nav aria-label=\{label\}>/)
  assert.match(files['parts.jsx'], /'aria-current': active \? 'page' : undefined/)
  assert.match(files['ModuleNav.jsx'], /active=\{item === active\}/)
  assert.match(files['ModuleNav.jsx'], /aria-labelledby=\{headingId\}/)
})

test('routed items are links, state-driven items are buttons, hosts may draw the link', () => {
  const parts = files['parts.jsx']
  assert.match(parts, /if \(item\.path === undefined\) \{\s*return \(\s*<button type="button"/)
  assert.match(parts, /renderLink \? renderLink\(\{ item, active, \.\.\.anchorProps \}\) : <a \{\.\.\.anchorProps\} \/>/)
  assert.match(parts, /href: item\.path/)
  assert.match(parts, /aria-hidden="true"/)
})

test('the shell provides a skip link, landmarks and a focusable main', () => {
  const shell = files['AppShell.jsx']
  assert.match(shell, /className="fd-shell__skip"/)
  assert.match(shell, /href=\{`#\$\{mainId\}`\}/)
  assert.match(shell, /<main id=\{mainId\} ref=\{mainRef\} tabIndex=\{-1\}/)
  assert.match(shell, /<header className="fd-shell__header">/)
  assert.match(shell, /if \(focusMainOnNavigate\) mainRef\.current\?\.focus\(\)/)
  // Focus moves only when `current` changes. A "have I mounted" flag is not
  // enough: StrictMode runs the effect twice on mount, and the second run
  // would take focus from the skip link on first load.
  assert.match(shell, /if \(lastCurrent\.current === current\) return/)
  assert.doesNotMatch(shell, /mounted\.current/)
  assert.match(shell, /data-mobile-below=\{mobileBelow\}/)
  assert.match(shell, /mobileBelow must be one of/)
  // DOM order is reading order: skip link, navigation, header, main.
  const order = ['fd-shell__skip', 'fd-shell__nav"', '<header', '<main', '<FederationMobileNav'].map((token) => shell.lastIndexOf(token))
  assert.deepEqual(order, [...order].sort((a, b) => a - b))
})

test('the More sheet is a native modal dialog that returns focus', () => {
  const mobile = files['MobileNav.jsx']
  assert.match(mobile, /dialog\.showModal\(\)/)
  assert.match(mobile, /aria-haspopup="dialog"/)
  assert.match(mobile, /aria-expanded=\{open\}/)
  assert.match(mobile, /aria-current=\{moreActive \? 'page' : undefined\}/)
  assert.match(mobile, /onClose=\{handleClose\}/)
  assert.match(mobile, /moreRef\.current\?\.focus\(\)/)
  assert.match(mobile, /onNavigate=\{close\}/)
  assert.match(mobile, /event\.target === event\.currentTarget/)
})

test('the inspector is one dialog with a docked and a modal presentation', () => {
  const inspector = files['InspectorPanel.jsx']
  assert.match(inspector, /requires a title/)
  assert.match(inspector, /aria-labelledby=\{titleId\}/)
  assert.match(inspector, /dialog\.showModal\(\)/)
  assert.match(inspector, /dialog\.show\(\)/)
  assert.match(inspector, /FEDERATION_SHELL_BREAKPOINTS\.desktop/)
  assert.match(inspector, /event\.key === 'Escape'/)
  assert.match(inspector, /opener\.focus\?\.\(\)/)
  assert.match(inspector, /addEventListener\?\.\('change', present\)/)
  assert.match(inspector, /removeEventListener\?\.\('change', present\)/)
})

test('a status bar is a live region only when asked', () => {
  assert.match(files['StatusBar.jsx'], /aria-live=\{live \? 'polite' : undefined\}/)
  assert.match(files['StatusBar.jsx'], /live = false/)
})

test('components follow the package conventions', () => {
  for (const name of ['AppShell.jsx', 'ModuleNav.jsx', 'MobileNav.jsx', 'InspectorPanel.jsx', 'StatusBar.jsx']) {
    assert.match(files[name], /export function Federation[A-Za-z]+\(\{/, `${name}: named function export`)
    assert.match(files[name], /className=\{cx\('fd-/, `${name}: fd- class on the root`)
    assert.match(files[name], /\{\.\.\.props\}/, `${name}: rest props reach the root`)
    assert.doesNotMatch(files[name], /forwardRef|\buse\(|useActionState|useOptimistic/, `${name}: must run on React 18`)
  }
})
