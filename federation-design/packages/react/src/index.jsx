import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'

function cx(...values) {
  return values.filter(Boolean).join(' ')
}

/*
 * Shared theme controller for the whole federation. It writes BOTH signals so
 * the two styling layers stay in agreement:
 *   - `.dark` class on <html>      → Tailwind `darkMode: ["class"]`
 *   - `data-theme="dark|light"`    → shared federation.css tokens
 * It also stamps `data-repo` so each app picks up its own accent from
 * federation.css. Preference resolves stored value → OS preference → light,
 * and is persisted per-repo so sibling apps don't fight over one key.
 */
const ThemeContext = createContext(null)

function resolveInitialTheme(storageKey) {
  if (typeof window === 'undefined') return 'light'
  const stored = window.localStorage.getItem(storageKey)
  if (stored === 'light' || stored === 'dark') return stored
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function FederationThemeProvider({ repo, defaultTheme, children }) {
  const storageKey = `fd-theme:${repo || 'default'}`
  const [theme, setThemeState] = useState(() => defaultTheme || resolveInitialTheme(storageKey))

  useEffect(() => {
    const root = document.documentElement
    root.classList.toggle('dark', theme === 'dark')
    root.dataset.theme = theme
    if (repo) root.dataset.repo = repo
    try { window.localStorage.setItem(storageKey, theme) } catch { /* private mode */ }
  }, [theme, repo, storageKey])

  const setTheme = useCallback((next) => setThemeState(next === 'dark' ? 'dark' : 'light'), [])
  const toggleTheme = useCallback(() => setThemeState((t) => (t === 'dark' ? 'light' : 'dark')), [])

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useFederationTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useFederationTheme must be used within a FederationThemeProvider')
  return ctx
}

export function FederationButton({ variant = 'primary', className, type = 'button', ...props }) {
  return <button type={type} className={cx('fd-button', `fd-button--${variant}`, 'fd-focus', className)} {...props} />
}

export function FederationPanel({ as: Component = 'section', className, ...props }) {
  return <Component className={cx('fd-panel', className)} {...props} />
}

// Canonical federation status vocabulary — the single shared set across the hub
// and producers (see federation.css --fd-st-* + thehub-pr src/lib/chips.js).
export const FEDERATION_STATUS_ROLES = [
  'danger', 'success', 'warning', 'info', 'neutral', 'process', 'tier', 'caution', 'elevated',
]

// Coarse node-health aliases → canonical roles, so existing `.fd-status` values keep working.
const STATUS_ALIASES = {
  operational: 'success', degraded: 'warning', critical: 'danger',
  offline: 'neutral', information: 'info', analysis: 'process',
}

// Resolve any status value (canonical role or alias) to a canonical role.
export function federationStatusRole(status) {
  const v = String(status || 'neutral').toLowerCase()
  return STATUS_ALIASES[v] || v
}

// Style your own element as a status pill without importing the badge component:
// <span {...federationTone('warning')}>…</span>
export function federationTone(status) {
  return { className: 'fd-status', 'data-status': federationStatusRole(status) }
}

export function FederationStatusBadge({ status, children, className, ...props }) {
  const role = federationStatusRole(status)
  return (
    <span className={cx('fd-status', `fd-status--${role}`, className)} data-status={role} {...props}>
      {children ?? String(status ?? role)}
    </span>
  )
}

// `icon` is an already-rendered node (e.g. a lucide element) — the package never
// imports an icon library, keeping it dependency-free.
//
// `inline` renders the compact variant: a single muted line sized to sit inside
// a dense pane or list, next to sibling status lines like "Loading…". The block
// variant (default) is the full centered treatment with the icon tile. Inline
// drops the heading level too — a one-line pane message shouldn't inject an
// <h2> into the document outline.
export function FederationEmptyState({ icon, title, description, action, inline, className, ...props }) {
  const Title = inline ? 'p' : 'h2'
  return (
    <div
      className={cx('fd-empty-state', inline && 'fd-empty-state--inline', className)}
      role="status"
      {...props}
    >
      {icon ? <div className="fd-empty-state__icon" aria-hidden="true">{icon}</div> : null}
      <Title className="fd-empty-state__title">{title}</Title>
      {description ? <p className="fd-empty-state__description">{description}</p> : null}
      {action ? <div className="fd-empty-state__action">{action}</div> : null}
    </div>
  )
}

// Metric tile. `value` is the headline figure; `icon` (optional) is a rendered
// node; `sub` an optional caption; `alert` tints the icon with the danger token.
//
// `tone` tints the *value* with a canonical status role (see
// FEDERATION_STATUS_ROLES), replacing the per-repo Tailwind literals producers
// used to pass (`text-emerald-300`, `text-amber-300`, …). Accepts aliases too,
// so `tone="operational"` resolves to `success`. Omit it for the default text
// color — untinted tiles stay untouched.
export function FederationStatCard({ label, value, icon, sub, alert, tone, className, ...props }) {
  return (
    <div className={cx('fd-stat-card', alert && 'fd-stat-card--alert', className)} {...props}>
      <div className="fd-stat-card__head">
        <span className="fd-stat-card__label">{label}</span>
        {icon ? <span className="fd-stat-card__icon" aria-hidden="true">{icon}</span> : null}
      </div>
      <div className="fd-stat-card__value" data-tone={tone ? federationStatusRole(tone) : undefined}>
        {value}
      </div>
      {sub ? <div className="fd-stat-card__sub">{sub}</div> : null}
    </div>
  )
}
