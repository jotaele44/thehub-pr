import React, { useId, useState } from 'react'
import { isNavCollection, matchFederationNavItem, navCollectionKey, normalizeNavPath, resolveNavLabel } from './nav.js'
import { NavEntry, cx } from './parts.jsx'
import { FederationItemMenu } from '../controls/Menu.jsx'
import { FederationScrollRegion } from '../controls/ScrollRegion.jsx'

// One pinned or recent entry: its link, its status mark (drawn by NavEntry)
// and, beside the link and never inside it, the menu of its actions.
function CollectionRow({ entry, open, shared }) {
  const label = resolveNavLabel(entry.label, shared.labelContext)
  return (
    <li className="fd-nav__row">
      <NavEntry item={entry} active={false} open={open} className="fd-nav__link" {...shared} />
      {Array.isArray(entry.actions) && entry.actions.length > 0 ? (
        <FederationItemMenu itemLabel={typeof label === 'string' ? label : String(entry.id)} items={entry.actions} />
      ) : null}
    </li>
  )
}

// A pinned or recent group. The first `maxItems` entries are shown; the
// group's `overflow` decides what happens to the rest.
function CollectionGroup({ group, entries, groupLabel, headingId, current, shared, moreLabel, lessLabel }) {
  const [expanded, setExpanded] = useState(false)
  const restId = useId()
  const isOpen = (entry) => typeof current === 'string' && current !== ''
    && (entry.path !== undefined ? normalizeNavPath(current) === normalizeNavPath(entry.path) : current === entry.id)
  const row = (entry) => <CollectionRow key={entry.id} entry={entry} open={isOpen(entry)} shared={shared} />
  const shown = group.overflow === 'scroll' ? entries : entries.slice(0, group.maxItems)
  const rest = group.overflow === 'more-submenu' ? entries.slice(group.maxItems) : []
  const list = <ul className="fd-nav__list" aria-labelledby={headingId}>{shown.map(row)}</ul>
  return (
    <div className="fd-nav__group" data-kind={group.kind}>
      <p className="fd-nav__group-label" id={headingId}>{groupLabel}</p>
      {group.overflow === 'scroll' ? (
        <FederationScrollRegion aria-labelledby={headingId} role="group" axis="y" className="fd-nav__scroll" style={{ '--fd-nav-rows': group.maxItems }}>
          {list}
        </FederationScrollRegion>
      ) : list}
      {rest.length > 0 ? (
        <>
          <button type="button" className="fd-nav__link fd-nav__more" aria-expanded={expanded} aria-controls={expanded ? restId : undefined} onClick={() => setExpanded((value) => !value)}>
            <span className="fd-nav__text"><span className="fd-nav__label">{expanded ? lessLabel : `${moreLabel} (${rest.length})`}</span></span>
          </button>
          {expanded ? <ul className="fd-nav__list" id={restId} aria-label={`${groupLabel}: ${moreLabel}`}>{rest.map(row)}</ul> : null}
        </>
      ) : null}
    </div>
  )
}

/**
 * The primary navigation: a labelled <nav> of grouped lists with exactly one
 * current page. `groups` is a registry from defineFederationNav; `current`
 * is the current path, or the id of the current state-driven view.
 *
 * `collections` supplies the entries of the registry's pinned and recent
 * groups, keyed by the group's id or kind:
 * `{ pinned: [{ id, label, path?, status?, actions? }] }`. A collection with
 * no entries is not drawn. The navigation stores nothing: the host owns the
 * lists and the actions.
 */
export function FederationModuleNav({
  groups,
  current,
  onSelect,
  onNavigate,
  renderLink,
  isActive,
  labelContext,
  collections,
  collectionMoreLabel = 'More',
  collectionLessLabel = 'Show fewer',
  label = 'Primary',
  className,
  ...props
}) {
  const baseId = useId()
  const active = matchFederationNavItem(groups, current, { isActive })
  const shared = { onSelect, onNavigate, renderLink, labelContext }
  return (
    <nav aria-label={label} className={cx('fd-nav', className)} {...props}>
      {(groups || []).map((group, index) => {
        const groupLabel = resolveNavLabel(group.label, labelContext)
        const headingId = groupLabel ? `${baseId}-group-${index}` : undefined
        if (isNavCollection(group)) {
          const entries = collections?.[navCollectionKey(group)] || []
          if (entries.length === 0) return null
          return (
            <CollectionGroup
              key={headingId}
              group={group}
              entries={entries}
              groupLabel={groupLabel}
              headingId={headingId}
              current={current}
              shared={shared}
              moreLabel={collectionMoreLabel}
              lessLabel={collectionLessLabel}
            />
          )
        }
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
