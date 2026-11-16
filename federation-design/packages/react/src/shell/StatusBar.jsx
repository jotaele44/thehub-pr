import React from 'react'
import { cx } from './parts.jsx'

/**
 * A labelled strip under the header for standing state: connection, data
 * freshness, mode. Pass `live` only for content that changes while the page
 * is open and is worth announcing; a static strip must not be a live region.
 */
export function FederationStatusBar({ label = 'Status', live = false, className, children, ...props }) {
  return (
    <section aria-label={label} aria-live={live ? 'polite' : undefined} className={cx('fd-status-bar', className)} {...props}>
      {children}
    </section>
  )
}
