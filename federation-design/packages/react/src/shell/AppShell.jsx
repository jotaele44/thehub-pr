import React, { useEffect, useRef } from 'react'
import { FEDERATION_SHELL_BREAKPOINTS } from './nav.js'
import { FederationMobileNav } from './MobileNav.jsx'
import { FederationModuleNav } from './ModuleNav.jsx'
import { cx } from './parts.jsx'

/**
 * The federation application shell (FEDERATION_GUI_STANDARD.md, section 4).
 *
 * A repository supplies content and a navigation registry; it does not fork
 * or restyle the shell. Slots: `header`, `navHeader`, `navFooter`,
 * `statusBar`, `inspector`, and `children` for the routed page.
 *
 * The shell knows nothing about routing. `current` is the current path (or
 * the id of the current state-driven view), `renderLink` draws a link with
 * the host's router, and `onSelect` handles items that have no path.
 */
export function FederationAppShell({
  nav,
  current,
  onSelect,
  renderLink,
  isActive,
  labelContext,
  collections,
  mobileBelow = 'tablet',
  navLabel = 'Primary',
  moreLabel = 'More',
  closeLabel = 'Close',
  skipLabel = 'Skip to main content',
  mainId = 'fd-main',
  focusMainOnNavigate = false,
  header,
  navHeader,
  navFooter,
  statusBar,
  inspector,
  className,
  children,
  ...props
}) {
  if (!Array.isArray(nav)) throw new Error('FederationAppShell requires nav: a registry from defineFederationNav')
  if (!Object.hasOwn(FEDERATION_SHELL_BREAKPOINTS, mobileBelow)) {
    throw new Error(`FederationAppShell mobileBelow must be one of: ${Object.keys(FEDERATION_SHELL_BREAKPOINTS).join(', ')}`)
  }
  const mainRef = useRef(null)
  const mounted = useRef(false)

  // After a navigation, a keyboard or screen-reader user is otherwise left
  // on the link they just activated, with nothing announcing the new page.
  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true
      return
    }
    if (focusMainOnNavigate) mainRef.current?.focus()
  }, [current, focusMainOnNavigate])

  const shared = { groups: nav, current, onSelect, renderLink, isActive, labelContext, collections, label: navLabel }

  return (
    <div className={cx('fd-shell', className)} data-mobile-below={mobileBelow} {...props}>
      <a
        className="fd-shell__skip"
        href={`#${mainId}`}
        onClick={(event) => {
          event.preventDefault()
          mainRef.current?.focus()
        }}
      >
        {skipLabel}
      </a>
      <div className="fd-shell__nav">
        {navHeader ? <div className="fd-shell__nav-header">{navHeader}</div> : null}
        <FederationModuleNav {...shared} />
        {navFooter ? <div className="fd-shell__nav-footer">{navFooter}</div> : null}
      </div>
      <header className="fd-shell__header">{header}</header>
      {statusBar ? <div className="fd-shell__status">{statusBar}</div> : null}
      <main id={mainId} ref={mainRef} tabIndex={-1} className="fd-shell__main">{children}</main>
      {inspector ? <div className="fd-shell__inspector">{inspector}</div> : null}
      <FederationMobileNav
        {...shared}
        className="fd-shell__mobile-nav"
        moreLabel={moreLabel}
        closeLabel={closeLabel}
        header={navHeader}
        footer={navFooter}
      />
    </div>
  )
}
