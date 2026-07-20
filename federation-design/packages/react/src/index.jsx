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

export function FederationStatusBadge({ status, children, className, ...props }) {
  const normalized = String(status || 'offline').toLowerCase()
  return (
    <span className={cx('fd-status', `fd-status--${normalized}`, className)} data-status={normalized} {...props}>
      {children ?? normalized}
    </span>
  )
}

export function FederationEmptyState({ title, description, action, className, ...props }) {
  return (
    <div className={cx('fd-empty-state', className)} role="status" {...props}>
      <h2 className="fd-empty-state__title">{title}</h2>
      {description ? <p className="fd-empty-state__description">{description}</p> : null}
      {action ? <div className="fd-empty-state__action">{action}</div> : null}
    </div>
  )
}
