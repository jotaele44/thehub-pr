import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import {
  FEDERATION_PRESENTATION_TONES,
  federationStatusRole,
  federationTone,
  resolveFederationSemantic,
} from './semantics.js'

export * from './semantics.js'

function cx(...values) {
  return values.filter(Boolean).join(' ')
}

const ThemeContext = createContext(null)

function resolveInitialTheme(storageKey) {
  if (typeof window === 'undefined') return 'light'
  const stored = window.localStorage.getItem(storageKey)
  if (stored === 'light' || stored === 'dark') return stored
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function FederationThemeProvider({ repo, defaultTheme, allowedThemes = ['light', 'dark'], children }) {
  const storageKey = `fd-theme:${repo || 'default'}`
  const initial = defaultTheme || resolveInitialTheme(storageKey)
  const [theme, setThemeState] = useState(() => allowedThemes.includes(initial) ? initial : allowedThemes[0] || 'light')

  useEffect(() => {
    const root = document.documentElement
    root.classList.toggle('dark', theme === 'dark')
    root.dataset.theme = theme
    if (repo) root.dataset.repo = repo
    try { window.localStorage.setItem(storageKey, theme) } catch { /* private mode */ }
  }, [theme, repo, storageKey])

  const setTheme = useCallback((next) => {
    if (allowedThemes.includes(next)) setThemeState(next)
  }, [allowedThemes])
  const toggleTheme = useCallback(() => {
    if (allowedThemes.length < 2) return
    setThemeState((current) => current === 'dark' ? 'light' : 'dark')
  }, [allowedThemes])

  return <ThemeContext.Provider value={{ theme, setTheme, toggleTheme, allowedThemes }}>{children}</ThemeContext.Provider>
}

export function useFederationTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useFederationTheme must be used within a FederationThemeProvider')
  return ctx
}

export function FederationButton({ variant = 'primary', className, type = 'button', loading = false, disabled, children, ...props }) {
  return (
    <button
      type={type}
      className={cx('fd-button', `fd-button--${variant}`, 'fd-focus', className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading ? <span className="fd-spinner" aria-hidden="true" /> : null}
      {children}
    </button>
  )
}

export function FederationIconButton({ label, 'aria-label': ariaLabel, className, type = 'button', children, ...props }) {
  const accessibleName = ariaLabel || label
  if (!accessibleName) throw new Error('FederationIconButton requires label or aria-label')
  return (
    <button type={type} className={cx('fd-icon-button', 'fd-focus', className)} aria-label={accessibleName} {...props}>
      <span aria-hidden="true">{children}</span>
    </button>
  )
}

export function FederationPanel({ as: Component = 'section', className, ...props }) {
  return <Component className={cx('fd-panel', className)} {...props} />
}

export const FEDERATION_STATUS_ROLES = FEDERATION_PRESENTATION_TONES
export { federationStatusRole, federationTone }

export function FederationSemanticBadge({ kind, value, label, children, className, ...props }) {
  const semantic = resolveFederationSemantic(kind, value)
  return (
    <span
      className={cx('fd-badge', className)}
      data-kind={semantic.kind}
      data-value={semantic.value}
      data-tone={semantic.tone}
      {...props}
    >
      {children ?? label ?? semantic.label}
    </span>
  )
}

export function FederationStatusBadge({ status, kind = 'operational', children, className, ...props }) {
  if (kind === 'presentation') {
    const tone = federationStatusRole(status)
    return <span className={cx('fd-badge', className)} data-kind="presentation" data-value={tone} data-tone={tone} {...props}>{children ?? String(status ?? tone)}</span>
  }
  return <FederationSemanticBadge kind={kind} value={status} className={className} {...props}>{children}</FederationSemanticBadge>
}

export function FederationEvidenceTierBadge({ tier = 'ungraded', ...props }) {
  return <FederationSemanticBadge kind="evidenceTier" value={tier} {...props} />
}

export function FederationConfidenceBadge({ confidence = 'unknown', ...props }) {
  return <FederationSemanticBadge kind="confidence" value={confidence} {...props} />
}

export function FederationProvenanceBadge({ state = 'missing', ...props }) {
  return <FederationSemanticBadge kind="provenance" value={state} {...props} />
}

export function FederationFreshnessBadge({ freshness = 'unknown', ...props }) {
  return <FederationSemanticBadge kind="freshness" value={freshness} {...props} />
}

export function FederationSourceBadge({ source, sourceId, verified = false, className, children, ...props }) {
  const text = children ?? source ?? sourceId ?? 'Unknown source'
  return (
    <span className={cx('fd-source-badge', className)} data-verified={verified ? 'true' : 'false'} {...props}>
      {text}
    </span>
  )
}

export function FederationEmptyState({ icon, title, description, action, inline, className, ...props }) {
  const Title = inline ? 'p' : 'h2'
  return (
    <div className={cx('fd-state', 'fd-state--empty', inline && 'fd-state--inline', className)} role="status" aria-live="polite" {...props}>
      {icon ? <div className="fd-state__icon" aria-hidden="true">{icon}</div> : null}
      <Title className="fd-state__title">{title}</Title>
      {description ? <p className="fd-state__description">{description}</p> : null}
      {action ? <div className="fd-state__action">{action}</div> : null}
    </div>
  )
}

function FederationStateMessage({ state, title, description, action, icon, inline, busy = false, className, ...props }) {
  const semantic = resolveFederationSemantic('asyncState', state)
  const role = semantic.value === 'error' ? 'alert' : 'status'
  const live = semantic.value === 'error' ? 'assertive' : 'polite'
  const Title = inline ? 'p' : 'h2'
  return (
    <div
      className={cx('fd-state', `fd-state--${semantic.value}`, inline && 'fd-state--inline', className)}
      data-tone={semantic.tone}
      role={role}
      aria-live={live}
      aria-busy={busy || undefined}
      {...props}
    >
      {icon ? <div className="fd-state__icon" aria-hidden="true">{icon}</div> : null}
      {semantic.value === 'loading' ? <span className="fd-spinner fd-state__spinner" aria-hidden="true" /> : null}
      <Title className="fd-state__title">{title ?? semantic.label}</Title>
      {description ? <p className="fd-state__description">{description}</p> : null}
      {action ? <div className="fd-state__action">{action}</div> : null}
    </div>
  )
}

export function FederationLoadingState(props) { return <FederationStateMessage state="loading" busy {...props} /> }
export function FederationErrorState(props) { return <FederationStateMessage state="error" {...props} /> }
export function FederationFilteredEmptyState(props) { return <FederationStateMessage state="filtered_empty" {...props} /> }
export function FederationOfflineState(props) { return <FederationStateMessage state="offline" {...props} /> }
export function FederationDegradedState(props) { return <FederationStateMessage state="degraded" {...props} /> }
export function FederationPartialDataState(props) { return <FederationStateMessage state="partial" {...props} /> }
export function FederationStaleDataState(props) { return <FederationStateMessage state="stale" {...props} /> }

export function FederationAsyncState({ state = 'idle', children, ...props }) {
  if (state === 'ready' || state === 'success') return children
  if (state === 'empty') return <FederationEmptyState {...props} />
  return <FederationStateMessage state={state} {...props} />
}

export function FederationStatCard({ label, value, icon, sub, alert, tone, className, ...props }) {
  return (
    <div className={cx('fd-stat-card', alert && 'fd-stat-card--alert', className)} {...props}>
      <div className="fd-stat-card__head">
        <span className="fd-stat-card__label">{label}</span>
        {icon ? <span className="fd-stat-card__icon" aria-hidden="true">{icon}</span> : null}
      </div>
      <div className="fd-stat-card__value" data-tone={tone ? federationStatusRole(tone) : undefined}>{value}</div>
      {sub ? <div className="fd-stat-card__sub">{sub}</div> : null}
    </div>
  )
}
