import React from 'react'
import { FEDERATION_SHELL_BREAKPOINTS } from '../shell/nav.js'
import { cx } from './util.js'

/**
 * A button label that gives way to its icon on small screens without taking
 * the button's name with it.
 *
 * Hiding a label with `display: none` removes it from the accessible name,
 * which leaves an icon-only button nameless. Below `hideBelow` this label is
 * clipped out of sight instead, so it is still the name.
 */
export function FederationResponsiveLabel({ hideBelow = 'tablet', className, children, ...props }) {
  if (!Object.hasOwn(FEDERATION_SHELL_BREAKPOINTS, hideBelow)) {
    throw new Error(`FederationResponsiveLabel hideBelow must be one of: ${Object.keys(FEDERATION_SHELL_BREAKPOINTS).join(', ')}`)
  }
  return <span className={cx('fd-responsive-label', className)} data-hide-below={hideBelow} {...props}>{children}</span>
}
