import React, { useCallback, useEffect, useRef, useState } from 'react'
import { FEDERATION_MOBILE_NAV_MAX, matchFederationNavItem, splitMobileNav } from './nav.js'
import { FederationModuleNav } from './ModuleNav.jsx'
import { NavEntry, cx } from './parts.jsx'

/**
 * The small-screen bottom bar: at most five entries. When the registry holds
 * more, the fifth is "More", which opens the rest in a native <dialog> (focus
 * is trapped and Escape closes it without any dependency). Selecting an entry
 * closes the sheet, and focus returns to "More" however it was closed.
 *
 * `header` and `footer` are host content shown inside the sheet (a theme
 * toggle, a status line). They are mounted only while it is open.
 */
export function FederationMobileNav({
  groups,
  current,
  onSelect,
  renderLink,
  isActive,
  labelContext,
  label = 'Primary',
  moreLabel = 'More',
  closeLabel = 'Close',
  max = FEDERATION_MOBILE_NAV_MAX,
  header,
  footer,
  className,
  ...props
}) {
  const [open, setOpen] = useState(false)
  const dialogRef = useRef(null)
  const moreRef = useRef(null)
  const active = matchFederationNavItem(groups, current, { isActive })
  const { primary, overflow, hasMore } = splitMobileNav(groups, { max, hasExtras: Boolean(header || footer) })
  const moreActive = Boolean(active) && !primary.includes(active)

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (open && !dialog.open) {
      if (typeof dialog.showModal === 'function') dialog.showModal()
      else dialog.setAttribute('open', '')
    } else if (!open && dialog.open) {
      if (typeof dialog.close === 'function') dialog.close()
      else dialog.removeAttribute('open')
    }
  }, [open])

  const close = useCallback(() => setOpen(false), [])
  // Fires for Escape as well as for close(), so focus always comes back.
  const handleClose = useCallback(() => {
    setOpen(false)
    moreRef.current?.focus()
  }, [])
  const shared = { onSelect, renderLink, labelContext }

  return (
    <div className={cx('fd-mobile-nav', className)} {...props}>
      <nav aria-label={label}>
        <ul className="fd-mobile-nav__list">
          {primary.map((item) => (
            <li key={item.id}>
              <NavEntry item={item} active={item === active} className="fd-mobile-nav__link" {...shared} />
            </li>
          ))}
          {hasMore ? (
            <li>
              <button
                ref={moreRef}
                type="button"
                className="fd-mobile-nav__link fd-mobile-nav__more"
                aria-haspopup="dialog"
                aria-expanded={open}
                aria-current={moreActive ? 'page' : undefined}
                onClick={() => setOpen(true)}
              >
                <span className="fd-nav__icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="2" /><circle cx="12" cy="12" r="2" /><circle cx="19" cy="12" r="2" /></svg>
                </span>
                <span className="fd-nav__text"><span className="fd-nav__label">{moreLabel}</span></span>
              </button>
            </li>
          ) : null}
        </ul>
      </nav>
      {hasMore ? (
        <dialog
          ref={dialogRef}
          className="fd-mobile-nav__sheet"
          aria-label={moreLabel}
          onClose={handleClose}
          onClick={(event) => { if (event.target === event.currentTarget) close() }}
        >
          <div className="fd-mobile-nav__sheet-header">
            <h2 className="fd-mobile-nav__sheet-title">{moreLabel}</h2>
            <button type="button" className="fd-mobile-nav__sheet-close" onClick={close}>{closeLabel}</button>
          </div>
          {open && header ? <div className="fd-mobile-nav__sheet-slot">{header}</div> : null}
          {overflow.length ? (
            <FederationModuleNav groups={overflow} current={current} isActive={isActive} label={moreLabel} onNavigate={close} {...shared} />
          ) : null}
          {open && footer ? <div className="fd-mobile-nav__sheet-slot">{footer}</div> : null}
        </dialog>
      ) : null}
    </div>
  )
}
