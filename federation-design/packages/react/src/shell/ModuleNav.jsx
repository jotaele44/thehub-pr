import React, { useId } from 'react'
import { matchFederationNavItem, resolveNavLabel } from './nav.js'
import { NavEntry, cx } from './parts.jsx'

/**
 * The primary navigation: a labelled <nav> of grouped lists with exactly one
 * current page. `groups` is a registry from defineFederationNav; `current`
 * is the current path, or the id of the current state-driven view.
 */
export function FederationModuleNav({
  groups,
  current,
  onSelect,
  onNavigate,
  renderLink,
  isActive,
  labelContext,
  label = 'Primary',
  className,
  ...props
}) {
  const baseId = useId()
  const active = matchFederationNavItem(groups, current, { isActive })
  return (
    <nav aria-label={label} className={cx('fd-nav', className)} {...props}>
      {(groups || []).map((group, index) => {
        const groupLabel = resolveNavLabel(group.label, labelContext)
        const headingId = groupLabel ? `${baseId}-group-${index}` : undefined
        return (
          <div className="fd-nav__group" key={headingId || index}>
            {groupLabel ? <p className="fd-nav__group-label" id={headingId}>{groupLabel}</p> : null}
            <ul className="fd-nav__list" aria-labelledby={headingId}>
              {group.items.map((item) => (
                <li key={item.id}>
                  <NavEntry
                    item={item}
                    active={item === active}
                    className="fd-nav__link"
                    onSelect={onSelect}
                    onNavigate={onNavigate}
                    renderLink={renderLink}
                    labelContext={labelContext}
                  />
                </li>
              ))}
            </ul>
          </div>
        )
      })}
    </nav>
  )
}
