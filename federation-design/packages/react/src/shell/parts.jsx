import React from 'react'
import { resolveNavLabel } from './nav.js'
import { FederationStatusMark } from '../controls/StatusMark.jsx'

export function cx(...values) {
  return values.filter(Boolean).join(' ')
}

// One navigation entry. A routed item is a link, drawn by the host's
// `renderLink` when it has a router and by a plain anchor when it does not; a
// state-driven item (no path) is a button. Both carry the same class, the
// same current-page marker and the same content, so the shell and the bottom
// bar cannot drift apart.
// `open` marks a pinned or recent entry that is the thing currently open; it
// is not the current page, which only a registry item can be.
export function NavEntry({ item, active, open, className, onSelect, onNavigate, renderLink, labelContext }) {
  const Icon = item.icon
  const label = resolveNavLabel(item.label, labelContext)
  const children = (
    <>
      {item.accent ? (
        <span className="fd-nav__dot" style={{ '--fd-nav-accent': item.accent }} aria-hidden="true" />
      ) : Icon ? (
        <span className="fd-nav__icon" aria-hidden="true"><Icon /></span>
      ) : null}
      <span className="fd-nav__text">
        {/* Labels are cut with an ellipsis when they do not fit; the title keeps the full text reachable. */}
        <span className="fd-nav__label" title={typeof label === 'string' ? label : undefined}>{label}</span>
        {item.description ? <span className="fd-nav__description">{item.description}</span> : null}
      </span>
      {item.status ? <FederationStatusMark {...item.status} /> : null}
    </>
  )
  const shared = {
    className,
    'aria-current': active ? 'page' : undefined,
    'data-active': active || undefined,
    'data-nav-id': item.id,
  }
  if (open && !active) {
    shared['aria-current'] = 'true'
    shared['data-active'] = true
  }
  if (item.path === undefined) {
    return (
      <button type="button" {...shared} onClick={() => { onSelect?.(item); onNavigate?.(item) }}>
        {children}
      </button>
    )
  }
  const anchorProps = { ...shared, href: item.path, onClick: () => onNavigate?.(item), children }
  return renderLink ? renderLink({ item, active, ...anchorProps }) : <a {...anchorProps} />
}
