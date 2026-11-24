// Navigation registry for the federation shell (FEDERATION_GUI_STANDARD.md §4).
//
// Pure logic, no React and no JSX, so it can be imported and tested without a
// transform and reused by anything that needs the registry: the shell, a
// command palette, a parity test that walks the routes.

// Mirrors tokens/federation.tokens.json `breakpoints`. CSS media queries
// cannot read custom properties, so shell.css repeats these as literals and a
// test keeps all three in step.
export const FEDERATION_SHELL_BREAKPOINTS = Object.freeze({ tablet: 768, desktop: 1280 })
export const FEDERATION_MOBILE_NAV_MAX = 5
// Groups whose entries the host supplies at render time (what a person
// pinned, what they opened last) instead of declaring them in the registry.
export const FEDERATION_NAV_COLLECTION_KINDS = Object.freeze(['pinned', 'recent'])
export const FEDERATION_NAV_OVERFLOW = Object.freeze(['more-submenu', 'scroll', 'none'])
export const FEDERATION_NAV_COLLECTION_MAX = 50
const DEFAULT_COLLECTION_ITEMS = 5

export const isNavCollection = (group) => Boolean(group) && FEDERATION_NAV_COLLECTION_KINDS.includes(group.kind)
// The key a host files a collection's entries under: the group's id, or its kind.
export const navCollectionKey = (group) => group.id || group.kind

const isLabel = (value) => (typeof value === 'string' && value.trim() !== '') || typeof value === 'function'
const isIcon = (value) => typeof value === 'function' || (typeof value === 'object' && value !== null)

function deepFreeze(value) {
  if (value && typeof value === 'object' && !Object.isFrozen(value) && (Array.isArray(value) || Object.getPrototypeOf(value) === Object.prototype)) {
    Object.freeze(value)
    for (const child of Object.values(value)) deepFreeze(child)
  }
  return value
}

// Query, hash and a trailing slash never change which page is current.
export function normalizeNavPath(value) {
  if (typeof value !== 'string') return ''
  const path = value.split(/[?#]/)[0]
  // A loop, not /\/+$/: that pattern backtracks quadratically on a long run
  // of slashes that is not at the end, and paths come from the address bar.
  let end = path.length
  while (end > 1 && path.charCodeAt(end - 1) === 47) end -= 1
  return path.slice(0, end)
}

/**
 * Validate and freeze a navigation registry.
 *
 * `groups` is `[{ label?, items: [{ label, path | id, icon?, capabilityId, ... }] }]`.
 * A group with `kind: 'pinned'` or `kind: 'recent'` declares no items: it
 * reserves a place for entries the host passes at render time, with
 * `maxItems` (1 to 50, default 5) shown and `overflow` deciding what happens
 * to the rest ('more-submenu', 'scroll' or 'none').
 * Every problem is collected and reported in one error, so a registry is
 * fixed in one pass instead of one throw at a time.
 */
export function defineFederationNav(groups, { requireCapabilityId = true } = {}) {
  const problems = []
  const ids = new Set()
  const paths = new Set()
  const collectionKeys = new Set()
  if (!Array.isArray(groups) || groups.length === 0) {
    throw new Error('defineFederationNav: groups must be a non-empty array')
  }
  const registry = groups.map((group, groupIndex) => {
    const where = `groups[${groupIndex}]`
    if (!group || typeof group !== 'object') {
      problems.push(`${where} must be an object`)
      return { items: [] }
    }
    if (group.label !== undefined && !isLabel(group.label)) problems.push(`${where}.label must be a non-empty string or a function`)
    if (group.kind !== undefined && group.kind !== 'static' && !FEDERATION_NAV_COLLECTION_KINDS.includes(group.kind)) {
      problems.push(`${where}.kind must be one of: static, ${FEDERATION_NAV_COLLECTION_KINDS.join(', ')}`)
      return { ...group, items: [] }
    }
    if (isNavCollection(group)) {
      if (!isLabel(group.label)) problems.push(`${where}.label is required for a ${group.kind} group`)
      if (group.items !== undefined) problems.push(`${where}.items must be omitted: a ${group.kind} group gets its entries at render time`)
      if (group.id !== undefined && (typeof group.id !== 'string' || group.id === '')) problems.push(`${where}.id must be a non-empty string`)
      const maxItems = group.maxItems === undefined ? DEFAULT_COLLECTION_ITEMS : group.maxItems
      if (!Number.isInteger(maxItems) || maxItems < 1 || maxItems > FEDERATION_NAV_COLLECTION_MAX) {
        problems.push(`${where}.maxItems must be a whole number from 1 to ${FEDERATION_NAV_COLLECTION_MAX}`)
      }
      const overflow = group.overflow === undefined ? 'more-submenu' : group.overflow
      if (!FEDERATION_NAV_OVERFLOW.includes(overflow)) problems.push(`${where}.overflow must be one of: ${FEDERATION_NAV_OVERFLOW.join(', ')}`)
      const key = navCollectionKey(group)
      if (collectionKeys.has(key)) problems.push(`${where} repeats the collection "${key}"; give one of them an id`)
      collectionKeys.add(key)
      return { ...group, maxItems, overflow, items: [] }
    }
    if (!Array.isArray(group.items) || group.items.length === 0) {
      problems.push(`${where}.items must be a non-empty array`)
      return { ...group, items: [] }
    }
    const items = group.items.map((item, itemIndex) => {
      const at = `${where}.items[${itemIndex}]`
      if (!item || typeof item !== 'object') {
        problems.push(`${at} must be an object`)
        return item
      }
      if (!isLabel(item.label)) problems.push(`${at}.label must be a non-empty string or a function`)
      const hasPath = item.path !== undefined
      if (hasPath && (typeof item.path !== 'string' || !item.path.startsWith('/'))) problems.push(`${at}.path must be a string starting with "/"`)
      if (item.id !== undefined && (typeof item.id !== 'string' || item.id === '')) problems.push(`${at}.id must be a non-empty string`)
      if (!hasPath && item.id === undefined) problems.push(`${at} needs a path (a routed page) or an id (a state-driven view)`)
      const path = hasPath && typeof item.path === 'string' ? normalizeNavPath(item.path) : undefined
      const id = typeof item.id === 'string' && item.id !== '' ? item.id : path
      if (id !== undefined) {
        if (ids.has(id)) problems.push(`${at} repeats id "${id}"`)
        ids.add(id)
      }
      if (path !== undefined) {
        if (paths.has(path)) problems.push(`${at} repeats path "${path}"`)
        paths.add(path)
      }
      if (item.icon !== undefined && !isIcon(item.icon)) problems.push(`${at}.icon must be a component`)
      if (requireCapabilityId && (typeof item.capabilityId !== 'string' || item.capabilityId === '')) {
        problems.push(`${at}.capabilityId is required: it names this entry's capability in .federation/gui-capabilities.json`)
      } else if (item.capabilityId !== undefined && (typeof item.capabilityId !== 'string' || item.capabilityId === '')) {
        problems.push(`${at}.capabilityId must be a non-empty string`)
      }
      if (item.end !== undefined && typeof item.end !== 'boolean') problems.push(`${at}.end must be a boolean`)
      if (item.match !== undefined && !(Array.isArray(item.match) && item.match.every((value) => typeof value === 'string' && value.startsWith('/')))) {
        problems.push(`${at}.match must be an array of paths starting with "/"`)
      }
      if (item.accent !== undefined && (typeof item.accent !== 'string' || item.accent === '')) problems.push(`${at}.accent must be a CSS colour value`)
      if (item.description !== undefined && typeof item.description !== 'string') problems.push(`${at}.description must be a string`)
      if (item.mobile !== undefined && item.mobile !== 'primary') problems.push(`${at}.mobile may only be "primary"`)
      // Unknown keys pass through untouched: hosts hang their own data on
      // items (search keywords, badges) and get it back from flatten/match.
      return { ...item, ...(path !== undefined ? { path } : {}), id }
    })
    return { ...group, items }
  })
  if (problems.length) {
    throw new Error(`defineFederationNav: ${problems.length} problem(s)\n- ${problems.join('\n- ')}`)
  }
  return deepFreeze(registry)
}

// Labels may be functions so translated apps resolve them at render time.
export function resolveNavLabel(label, context) {
  return typeof label === 'function' ? label(context) : label
}

/** Every item in registry order, with its group. The feed for a command palette. */
export function flattenFederationNav(registry, { labelContext } = {}) {
  const out = []
  for (const group of registry || []) {
    const groupLabel = resolveNavLabel(group.label, labelContext)
    for (const item of group.items || []) {
      out.push({
        id: item.id,
        path: item.path,
        label: resolveNavLabel(item.label, labelContext),
        groupLabel,
        icon: item.icon,
        capabilityId: item.capabilityId,
        item,
      })
    }
  }
  return out
}

// Length of the part of `current` this item claims, or -1 for no claim.
// Segment-aware: "/money" does not claim "/moneysweep".
function claim(item, current) {
  if (item.path === undefined) return item.id === current ? Number.MAX_SAFE_INTEGER : -1
  const candidates = item.end || item.path === '/' ? [] : [item.path]
  let best = current === item.path ? item.path.length : -1
  for (const prefix of [...candidates, ...(item.match || []).map(normalizeNavPath)]) {
    if (current === prefix || current.startsWith(prefix === '/' ? '/' : `${prefix}/`)) best = Math.max(best, prefix.length)
  }
  return best
}

/**
 * The one active item for `current` (a path, or the id of a state-driven
 * view), or null. The longest claim wins, so "/space-track/sky" selects its
 * own entry and not "/space-track". A host `isActive(item, current)` replaces
 * the per-item test; the longest-path tie-break still applies.
 */
export function matchFederationNavItem(registry, current, { isActive } = {}) {
  if (typeof current !== 'string' || current === '') return null
  const normalized = current.startsWith('/') ? normalizeNavPath(current) : current
  let winner = null
  let winnerScore = -1
  for (const group of registry || []) {
    for (const item of group.items || []) {
      const score = isActive
        ? (isActive(item, normalized) ? (item.path ? item.path.length : Number.MAX_SAFE_INTEGER) : -1)
        : claim(item, normalized)
      if (score > winnerScore) {
        winner = item
        winnerScore = score
      }
    }
  }
  return winner
}

/**
 * Split a registry for the small-screen bottom bar.
 *
 * The bar holds at most five entries. When everything fits, everything is
 * primary. Otherwise the fifth entry is "More": four items are primary
 * (those marked `mobile: 'primary'` first, then registry order) and the rest
 * are returned as overflow, still grouped. `hasExtras` forces a "More" entry
 * when the host has non-navigation content to put behind it.
 */
export function splitMobileNav(registry, { max = FEDERATION_MOBILE_NAV_MAX, hasExtras = false, collections } = {}) {
  const limit = Math.max(2, Math.min(FEDERATION_MOBILE_NAV_MAX, Math.floor(max) || FEDERATION_MOBILE_NAV_MAX))
  const all = (registry || []).flatMap((group) => group.items || [])
  // Pinned and recent entries never take a slot on the bar; a collection that
  // has entries lives behind "More", which it therefore forces.
  const filled = (group) => isNavCollection(group) && (collections?.[navCollectionKey(group)] || []).length > 0
  const collected = (registry || []).filter(filled)
  if (all.length <= limit && !hasExtras && collected.length === 0) return { primary: all, overflow: [], hasMore: false }
  const slots = limit - 1
  const preferred = all.filter((item) => item.mobile === 'primary')
  const chosen = new Set([...preferred, ...all.filter((item) => item.mobile !== 'primary')].slice(0, slots))
  const primary = all.filter((item) => chosen.has(item))
  const overflow = (registry || [])
    .map((group) => ({ ...group, items: (group.items || []).filter((item) => !chosen.has(item)) }))
    .filter((group) => group.items.length > 0 || filled(group))
  return { primary, overflow, hasMore: true }
}
