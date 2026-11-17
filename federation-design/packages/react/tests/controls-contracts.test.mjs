// Source contracts for the control primitives. As with the shell, components
// are not rendered here (the package has no JSX transform); they are rendered
// and driven from the keyboard by fixture-lab/tests/runtime-matrix.mjs. These
// tests pin the accessibility decisions a refactor must not lose.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { BUNDLED_STYLES, pkgRoot, publicExports, stylePath } from '../scripts/sources.mjs'
import { FEDERATION_SHELL_BREAKPOINTS } from '../src/shell/nav.js'

const dir = join(pkgRoot, 'src', 'controls')
const files = Object.fromEntries(readdirSync(dir).sort().map((name) => [name, readFileSync(join(dir, name), 'utf8')]))
const all = Object.values(files).join('\n')
const css = readFileSync(stylePath('controls.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
const shell = (name) => readFileSync(join(pkgRoot, 'src', 'shell', name), 'utf8')

test('the controls export exactly their documented surface', () => {
  const exported = publicExports()
  for (const name of [
    'FederationScrollRegion', 'FederationResponsiveLabel', 'FederationStatusMark', 'FederationTextField',
    'FederationDialog', 'FederationRenameDialog', 'FederationMenu', 'FederationItemMenu',
  ]) assert.ok(exported.has(name), `${name} is not exported`)
  for (const internal of ['useScrollable', 'cx']) assert.ok(!exported.has(internal), `${internal} leaked into the public API`)
})

test('the controls depend on React and this package only, and run on React 18', () => {
  const imports = [...all.matchAll(/from\s+'([^']+)'/g)].map((match) => match[1])
  for (const source of imports) {
    assert.ok(source === 'react' || source.startsWith('./') || source === '../shell/nav.js' || source === '../semantics.js', `unexpected import: ${source}`)
  }
  assert.doesNotMatch(all, /forwardRef|\buse\(|useActionState|useOptimistic/)
  assert.doesNotMatch(all, /localStorage|sessionStorage|indexedDB|fetch\(/, 'controls store nothing and call nothing')
})

test('a scroll region is named, and a tab stop only while the keyboard needs it', () => {
  const source = files['ScrollRegion.jsx']
  assert.match(source, /requires label, aria-label or aria-labelledby/)
  assert.match(source, /tabIndex=\{scrollable \? 0 : undefined\}/)
  assert.match(source, /scrollHeight > node\.clientHeight \+ 1 \|\| node\.scrollWidth > node\.clientWidth \+ 1/)
  assert.match(source, /&& !node\.querySelector\(FOCUSABLE\)/)
  assert.match(source, /observer\.disconnect\(\)/)
  assert.match(css, /\.fd-scroll-region:focus-visible/)
  // The one scrolling box in the package with nothing focusable inside it.
  assert.match(readFileSync(join(pkgRoot, 'src', 'gis', 'index.jsx'), 'utf8'), /aria-label="Dataset records" tabIndex=\{scrollable \? 0 : undefined\}/)
})

test('a responsive label is clipped, never removed, at the shell breakpoints', () => {
  assert.match(files['ResponsiveLabel.jsx'], /data-hide-below=\{hideBelow\}/)
  assert.match(files['ResponsiveLabel.jsx'], /hideBelow must be one of/)
  for (const [name, width] of Object.entries(FEDERATION_SHELL_BREAKPOINTS)) {
    assert.match(css, new RegExp(`@media \\(max-width: ${String(width - 0.02).replace('.', '\\.')}px\\) \\{\\s*\\.fd-responsive-label\\[data-hide-below="${name}"\\]`))
  }
  const block = css.slice(css.indexOf('.fd-responsive-label'), css.indexOf('.fd-status-mark'))
  assert.match(block, /clip-path: inset\(50%\)/)
  assert.doesNotMatch(block, /display:\s*none|visibility:\s*hidden/)
})

test('a status mark always has a text equivalent', () => {
  const source = files['StatusMark.jsx']
  assert.match(source, /requires label: the status in words/)
  assert.match(source, /role="img" aria-label=\{label\}/)
  assert.match(source, /className="fd-status-mark__glyph" aria-hidden="true"/)
  assert.match(source, /kind must be one of/)
  assert.match(source, /tone must be one of/)
  for (const kind of ['spinner', 'alert']) assert.match(css, new RegExp(`\\.fd-status-mark\\[data-kind="${kind}"\\]`))
})

test('a text field ties its label, help and error to the input', () => {
  const source = files['TextField.jsx']
  assert.match(source, /requires label/)
  assert.match(source, /<label className="fd-field__label" htmlFor=\{inputId\}>/)
  assert.match(source, /aria-invalid=\{error \? true : undefined\}/)
  assert.match(source, /aria-describedby=\{\[helpId, errorId\]\.filter\(Boolean\)\.join\(' '\) \|\| undefined\}/)
  assert.match(source, /id=\{errorId\} role="alert"/)
})

test('the dialog is a native modal that is labelled and returns focus', () => {
  const source = files['Dialog.jsx']
  assert.match(source, /requires a title/)
  assert.match(source, /dialog\.showModal\(\)/)
  assert.match(source, /aria-labelledby=\{titleId\}/)
  assert.match(source, /aria-describedby=\{description \? descriptionId : undefined\}/)
  assert.match(source, /openerRef\.current = document\.activeElement/)
  // A late close event must not close a dialog that was opened again.
  assert.match(source, /if \(dialogRef\.current\?\.open\) return\s*const opener = openerRef\.current/)
  assert.match(source, /if \(adrift && opener\?\.isConnected\) opener\.focus\?\.\(\)/)
  assert.match(source, /active === document\.body \|\| dialogRef\.current\?\.contains\(active\)/)
  assert.match(source, /if \(!dismissible\) event\.preventDefault\(\)/)
  assert.match(source, /event\.target === event\.currentTarget/)
  assert.match(source, /\[data-autofocus\]/)
})

test('rename validates, reports a failed save and stores nothing', () => {
  const source = files['RenameDialog.jsx']
  assert.match(source, /requires onRename/)
  assert.match(source, /const name = value\.trim\(\)/)
  assert.match(source, /name === \'\'\s*\? emptyMessage/)
  assert.match(source, /name\.length > maxLength/)
  assert.match(source, /disabled=\{saving \|\| unchanged\}/)
  assert.match(source, /await onRename\(name\)\s*\} catch \(failure\) \{\s*setSaving\(false\)\s*setError\(/)
  assert.match(source, /setSaving\(false\)\s*onClose\?\.\(\)/)
  // The form exists only while open, so no edit survives a cancel.
  assert.match(source, /\{open \? \(\s*<RenameForm/)
  assert.match(source, /dismissible=\{!saving\}/)
  assert.match(source, /data-autofocus=""/)
})

test('the menu follows the menu-button keyboard pattern and returns focus', () => {
  const source = files['Menu.jsx']
  assert.match(source, /requires label or aria-label/)
  assert.match(source, /aria-haspopup="menu"/)
  assert.match(source, /aria-expanded=\{open\}/)
  assert.match(source, /role="menu"/)
  assert.match(source, /role="menuitem"\s*tabIndex=\{-1\}/)
  for (const key of ['ArrowDown', 'ArrowUp', 'Home', 'End', 'Escape', 'Tab']) assert.match(source, new RegExp(`event\\.key === '${key}'`), key)
  assert.match(source, /event\.stopPropagation\(\)\s*close\(true\)/)
  assert.match(source, /if \(returnFocus\) triggerRef\.current\?\.focus\(\)/)
  assert.match(source, /addEventListener\('pointerdown', outside, true\)/)
  assert.match(source, /removeEventListener\('pointerdown', outside, true\)/)
  assert.match(source, /if \(item\.disabled\) return/)
})

test('an item menu is named after the item it acts on', () => {
  assert.match(files['Menu.jsx'], /requires itemLabel: the name of the item it acts on/)
  assert.match(files['Menu.jsx'], /aria-label=\{label \|\| `Actions for \$\{itemLabel\}`\}/)
  assert.match(files['Menu.jsx'], /aria-hidden="true" focusable="false"/)
})

test('pinned and recent entries keep one current page and put actions beside the link', () => {
  const nav = shell('ModuleNav.jsx')
  const parts = shell('parts.jsx')
  // An open pinned entry is marked, but never as a second current page.
  assert.match(nav, /<NavEntry item=\{entry\} active=\{false\} open=\{open\}/)
  assert.match(parts, /if \(open && !active\) \{\s*shared\['aria-current'\] = 'true'/)
  // The item menu is a sibling of the link: a button inside a link is invalid.
  assert.match(nav, /<li className="fd-nav__row">\s*<NavEntry[^>]*\/>\s*\{Array\.isArray\(entry\.actions\)/)
  assert.match(nav, /if \(entries\.length === 0\) return null/)
  assert.match(nav, /aria-expanded=\{expanded\}/)
  assert.match(parts, /\{item\.status \? <FederationStatusMark \{\.\.\.item\.status\} \/> : null\}/)
})

test('controls.css ships in the bundle and every rule is scoped', () => {
  assert.ok(BUNDLED_STYLES.includes('controls.css'))
  assert.match(readFileSync(stylePath('federation.css'), 'utf8'), /@import "\.\/controls\.css";/)
  const selectors = [...css.matchAll(/(^|\})\s*([^{}@]+)\{/g)].map((match) => match[2].trim()).filter(Boolean)
  assert.ok(selectors.length > 30, `parsed only ${selectors.length} rules`)
  for (const selector of selectors) {
    for (const part of selector.split(',')) assert.ok(part.trim().startsWith('.fd-'), `unscoped rule: ${selector}`)
  }
  assert.match(css, /forced-colors: active/)
  assert.doesNotMatch(css, /var\(--fd-accent\)(?!\))/, 'the raw accent appears only as a fallback')
})
