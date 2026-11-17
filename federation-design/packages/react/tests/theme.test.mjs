import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { pkgRoot } from '../scripts/sources.mjs'
import { resolveFederationTheme } from '../src/theme.js'

test('a saved preference wins over the application default and the system', () => {
  assert.equal(resolveFederationTheme({ stored: 'light', defaultTheme: 'dark', prefersDark: true }), 'light')
  assert.equal(resolveFederationTheme({ stored: 'dark', defaultTheme: 'light', prefersDark: false }), 'dark')
})

test('the application default applies to a new visitor, whatever the system prefers', () => {
  assert.equal(resolveFederationTheme({ defaultTheme: 'dark', prefersDark: false }), 'dark')
  assert.equal(resolveFederationTheme({ stored: null, defaultTheme: 'light', prefersDark: true }), 'light')
})

test('with no saved preference and no default, the system preference decides', () => {
  assert.equal(resolveFederationTheme({ prefersDark: true }), 'dark')
  assert.equal(resolveFederationTheme({ prefersDark: false }), 'light')
  assert.equal(resolveFederationTheme(), 'light')
})

test('values outside allowedThemes are ignored at every step', () => {
  assert.equal(resolveFederationTheme({ stored: 'sepia', defaultTheme: 'dark' }), 'dark')
  assert.equal(resolveFederationTheme({ stored: 'light', defaultTheme: 'light', prefersDark: false, allowedThemes: ['dark'] }), 'dark')
  assert.equal(resolveFederationTheme({ stored: 'dark', allowedThemes: ['light'] }), 'light')
  assert.equal(resolveFederationTheme({ defaultTheme: 'blue', prefersDark: true }), 'dark')
})

test('the provider resolves its first theme through resolveFederationTheme', () => {
  const source = readFileSync(join(pkgRoot, 'src', 'index.jsx'), 'utf8')
  assert.match(source, /import \{ resolveFederationTheme \} from '\.\/theme\.js'/)
  assert.match(source, /useState\(\(\) => readInitialTheme\(storageKey, defaultTheme, allowedThemes\)\)/)
  assert.doesNotMatch(source, /defaultTheme \|\|/)
})
