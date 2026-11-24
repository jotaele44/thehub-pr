import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { designRoot } from '../scripts/sources.mjs'
import {
  FEDERATION_MOBILE_NAV_MAX,
  FEDERATION_SHELL_BREAKPOINTS,
  defineFederationNav,
  flattenFederationNav,
  matchFederationNavItem,
  normalizeNavPath,
  resolveNavLabel,
  splitMobileNav,
} from '../src/shell/nav.js'

const Icon = () => null
const item = (path, extra = {}) => ({ label: path, path, capabilityId: `cap${path.replaceAll('/', '-')}`, ...extra })
const hub = () => defineFederationNav([
  { label: 'Overview', items: [item('/', { match: ['/activity'] }), item('/hub', { accent: '#0529a8' }), item('/search')] },
  { label: 'Producers', items: [item('/money'), item('/moneysweep'), item('/space-track'), item('/space-track/sky')] },
])

test('a valid registry is returned deep-frozen with ids filled in', () => {
  const nav = hub()
  assert.equal(nav[0].items[1].id, '/hub')
  assert.ok(Object.isFrozen(nav) && Object.isFrozen(nav[0]) && Object.isFrozen(nav[0].items) && Object.isFrozen(nav[0].items[0]))
  assert.throws(() => { nav[0].items[0].label = 'x' }, TypeError)
})

test('every violation is reported in one error', () => {
  assert.throws(
    () => defineFederationNav([
      { label: 'A', items: [
        { label: '', path: '/a', capabilityId: 'a' },
        { label: 'B', path: 'b', capabilityId: 'b' },
        { label: 'C', capabilityId: 'c' },
        { label: 'D', path: '/d' },
        { label: 'E', path: '/a', capabilityId: 'e', mobile: 'always', end: 'yes', match: ['x'], accent: 3 },
      ] },
      { label: 'Empty', items: [] },
    ]),
    (error) => {
      const text = error.message
      assert.match(text, /^defineFederationNav: \d+ problem\(s\)\n- /)
      for (const fragment of [
        'items[0].label must be',
        'items[1].path must be a string starting with "/"',
        'items[2] needs a path',
        'items[3].capabilityId is required',
        'repeats path "/a"',
        '.mobile may only be "primary"',
        '.end must be a boolean',
        '.match must be an array',
        '.accent must be a CSS colour value',
        'groups[1].items must be a non-empty array',
      ]) assert.ok(text.includes(fragment), `missing: ${fragment}\n${text}`)
      return true
    },
  )
  assert.throws(() => defineFederationNav([]), /non-empty array/)
  assert.throws(() => defineFederationNav(null), /non-empty array/)
})

test('capabilityId can be waived only explicitly, for migration', () => {
  const groups = [{ items: [{ label: 'A', path: '/a' }] }]
  assert.throws(() => defineFederationNav(groups), /capabilityId is required/)
  assert.equal(defineFederationNav(groups, { requireCapabilityId: false })[0].items[0].path, '/a')
})

test('ids and paths are unique across groups; state-driven items need only an id', () => {
  assert.throws(
    () => defineFederationNav([{ items: [item('/a')] }, { items: [item('/a/')] }]),
    /repeats (id|path) "\/a"/,
  )
  const nav = defineFederationNav([{ items: [{ label: 'Cases', id: 'cases', capabilityId: 'cases' }, { label: 'Map', id: 'map', capabilityId: 'map' }] }])
  assert.equal(nav[0].items[0].path, undefined)
  assert.equal(matchFederationNavItem(nav, 'map').id, 'map')
  assert.equal(matchFederationNavItem(nav, 'unknown'), null)
})

test('icons may be function or forwardRef-object components; unknown keys survive', () => {
  const nav = defineFederationNav([{ items: [item('/a', { icon: Icon, keywords: ['x'] }), item('/b', { icon: { $$typeof: Symbol.for('react.forward_ref') } })] }])
  assert.deepEqual(nav[0].items[0].keywords, ['x'])
  assert.throws(() => defineFederationNav([{ items: [item('/a', { icon: 'star' })] }]), /icon must be a component/)
})

test('labels may be functions and are never called at definition time', () => {
  let calls = 0
  const nav = defineFederationNav([{ label: (ctx) => ctx.lang, items: [item('/a', { label: (ctx) => { calls += 1; return ctx.lang === 'es' ? 'Señales' : 'Signals' } })] }])
  assert.equal(calls, 0)
  assert.equal(resolveNavLabel(nav[0].items[0].label, { lang: 'es' }), 'Señales')
  const flat = flattenFederationNav(nav, { labelContext: { lang: 'en' } })
  assert.deepEqual([flat[0].label, flat[0].groupLabel], ['Signals', 'en'])
})

test('flatten yields every item in order with its capability and original item', () => {
  const flat = flattenFederationNav(hub())
  assert.deepEqual(flat.map((entry) => entry.path), ['/', '/hub', '/search', '/money', '/moneysweep', '/space-track', '/space-track/sky'])
  assert.equal(flat[1].groupLabel, 'Overview')
  assert.equal(flat[1].capabilityId, 'cap-hub')
  assert.equal(flat[1].item.accent, '#0529a8')
})

test('paths are normalized: query, hash and trailing slash do not matter', () => {
  assert.equal(normalizeNavPath('/a/b/?x=1#y'), '/a/b')
  assert.equal(normalizeNavPath('/'), '/')
  assert.equal(normalizeNavPath('/?tab=1'), '/')
  assert.equal(normalizeNavPath('/a///'), '/a')
  assert.equal(normalizeNavPath('///'), '/')
  assert.equal(normalizeNavPath(''), '')
  assert.equal(normalizeNavPath('a/'), 'a')
  assert.equal(normalizeNavPath(undefined), '')
  assert.equal(matchFederationNavItem(hub(), '/hub/?q=1#top').path, '/hub')
})

test('normalizing a hostile path is linear, not quadratic', () => {
  // 200k slashes followed by a non-slash: the shape that makes /\/+$/ crawl.
  const hostile = `${'/'.repeat(200_000)}x`
  const started = performance.now()
  assert.equal(normalizeNavPath(hostile), hostile)
  assert.equal(normalizeNavPath(`/a${'/'.repeat(200_000)}`), '/a')
  assert.ok(performance.now() - started < 250, 'normalizeNavPath took too long')
  assert.equal(matchFederationNavItem(hub(), hostile), null)
})

test('matching is segment-aware and the longest claim wins', () => {
  const nav = hub()
  const active = (current) => matchFederationNavItem(nav, current)?.path
  assert.equal(active('/moneysweep'), '/moneysweep')
  assert.equal(active('/moneysweep/contracts/42'), '/moneysweep')
  assert.equal(active('/money'), '/money')
  assert.equal(active('/space-track/sky/7'), '/space-track/sky')
  assert.equal(active('/space-track/ground'), '/space-track')
  assert.equal(active('/nowhere'), undefined)
})

test('the root item matches only itself, plus its declared extra prefixes', () => {
  const nav = hub()
  assert.equal(matchFederationNavItem(nav, '/').path, '/')
  assert.equal(matchFederationNavItem(nav, '/activity').path, '/')
  assert.equal(matchFederationNavItem(nav, '/activity/today').path, '/')
  assert.equal(matchFederationNavItem(nav, '/search').path, '/search')
})

test('end makes an item match exactly', () => {
  const nav = defineFederationNav([{ items: [item('/assets', { end: true }), item('/assets/map')] }])
  assert.equal(matchFederationNavItem(nav, '/assets').path, '/assets')
  assert.equal(matchFederationNavItem(nav, '/assets/42'), null)
  assert.equal(matchFederationNavItem(nav, '/assets/map/3').path, '/assets/map')
})

test('a host isActive replaces the per-item test but not the tie-break', () => {
  const nav = hub()
  const isActive = (entry, current) => current.startsWith('/space') && entry.path.startsWith('/space')
  assert.equal(matchFederationNavItem(nav, '/spaceship', { isActive }).path, '/space-track/sky')
  assert.equal(matchFederationNavItem(nav, '/hub', { isActive }), null)
  assert.equal(matchFederationNavItem(nav, ''), null)
  assert.equal(matchFederationNavItem(nav, undefined), null)
})

test('the mobile bar shows everything when it fits', () => {
  const nav = defineFederationNav([{ items: ['/a', '/b', '/c', '/d', '/e'].map((path) => item(path)) }])
  const split = splitMobileNav(nav)
  assert.equal(split.primary.length, 5)
  assert.deepEqual(split.overflow, [])
  assert.equal(split.hasMore, false)
})

test('beyond five entries the fifth is More and the rest keep their groups', () => {
  const split = splitMobileNav(hub())
  assert.equal(FEDERATION_MOBILE_NAV_MAX, 5)
  assert.deepEqual(split.primary.map((entry) => entry.path), ['/', '/hub', '/search', '/money'])
  assert.equal(split.hasMore, true)
  assert.deepEqual(split.overflow.map((group) => [group.label, group.items.map((entry) => entry.path)]), [
    ['Producers', ['/moneysweep', '/space-track', '/space-track/sky']],
  ])
})

test('items marked primary take bar slots first, in registry order', () => {
  const nav = defineFederationNav([{ items: ['/a', '/b', '/c', '/d', '/e', '/f'].map((path) => item(path, path === '/f' || path === '/e' ? { mobile: 'primary' } : {})) }])
  assert.deepEqual(splitMobileNav(nav).primary.map((entry) => entry.path), ['/a', '/b', '/e', '/f'])
})

test('host extras force a More entry, and the bar never exceeds five', () => {
  const nav = defineFederationNav([{ items: ['/a', '/b', '/c', '/d', '/e'].map((path) => item(path)) }])
  const split = splitMobileNav(nav, { hasExtras: true })
  assert.equal(split.primary.length, 4)
  assert.equal(split.hasMore, true)
  assert.equal(splitMobileNav(hub(), { max: 99 }).primary.length, 4)
  assert.equal(splitMobileNav(hub(), { max: 3 }).primary.length, 2)
})

test('shell breakpoints are the token breakpoints', () => {
  const tokens = JSON.parse(readFileSync(join(designRoot, 'tokens', 'federation.tokens.json'), 'utf8'))
  assert.equal(`${FEDERATION_SHELL_BREAKPOINTS.tablet}px`, tokens.breakpoints.tablet)
  assert.equal(`${FEDERATION_SHELL_BREAKPOINTS.desktop}px`, tokens.breakpoints.desktop)
  assert.ok(Object.isFrozen(FEDERATION_SHELL_BREAKPOINTS))
})

test('pinned and recent groups are declared without items and get their defaults', () => {
  const nav = defineFederationNav([
    { label: 'Overview', items: [item('/')] },
    { kind: 'pinned', label: 'Pinned' },
    { kind: 'recent', label: 'Recent', maxItems: 3, overflow: 'scroll', setting_id: 'nav.recents' },
  ])
  assert.deepEqual([nav[1].kind, nav[1].maxItems, nav[1].overflow, nav[1].items], ['pinned', 5, 'more-submenu', []])
  assert.deepEqual([nav[2].maxItems, nav[2].overflow, nav[2].setting_id], [3, 'scroll', 'nav.recents'])
  assert.ok(Object.isFrozen(nav[1]))
  // A collection contributes nothing to the registry's own items.
  assert.equal(flattenFederationNav(nav).length, 1)
  assert.equal(matchFederationNavItem(nav, '/').path, '/')
})

test('a malformed pinned or recent group is rejected, with every problem named', () => {
  assert.throws(() => defineFederationNav([
    { label: 'Overview', items: [item('/')] },
    { kind: 'pinned' },
    { kind: 'recent', label: 'Recent', items: [item('/x')], maxItems: 0, overflow: 'wrap' },
    { kind: 'recent', label: 'Again' },
    { kind: 'starred', label: 'Starred' },
  ]), (error) => {
    for (const fragment of [
      'groups[1].label is required for a pinned group',
      'groups[2].items must be omitted',
      'groups[2].maxItems must be a whole number from 1 to 50',
      'groups[2].overflow must be one of: more-submenu, scroll, none',
      'groups[3] repeats the collection "recent"',
      'groups[4].kind must be one of: static, pinned, recent',
    ]) assert.ok(error.message.includes(fragment), `missing: ${fragment}\n${error.message}`)
    return true
  })
  assert.doesNotThrow(() => defineFederationNav([
    { label: 'Overview', items: [item('/')] },
    { kind: 'recent', label: 'Recent cases', id: 'recent-cases' },
    { kind: 'recent', label: 'Recent searches', id: 'recent-searches' },
  ]))
})

test('a collection with entries sits behind More on the mobile bar, an empty one does not', () => {
  const nav = defineFederationNav([
    { label: 'Overview', items: [item('/'), item('/hub')] },
    { kind: 'pinned', label: 'Pinned' },
  ])
  assert.deepEqual(splitMobileNav(nav).hasMore, false)
  assert.deepEqual(splitMobileNav(nav, { collections: { pinned: [] } }).hasMore, false)
  const split = splitMobileNav(nav, { collections: { pinned: [{ id: 'case-1', label: 'Case 1' }] } })
  assert.equal(split.hasMore, true)
  assert.deepEqual(split.primary.map((entry) => entry.path), ['/', '/hub'])
  assert.deepEqual(split.overflow.map((group) => group.kind), ['pinned'])
})
