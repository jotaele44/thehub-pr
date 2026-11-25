import React, { useEffect, useRef, useState } from 'react'
import { cx } from './util.js'

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * Whether `ref`'s element needs to be a tab stop to be scrolled from the
 * keyboard: it has content to scroll and nothing focusable inside it.
 *
 * A container that scrolls and holds nothing focusable cannot be scrolled
 * from the keyboard unless it is itself a tab stop. Making every such
 * container a permanent tab stop adds stops that do nothing, so the stop is
 * present only while it is needed.
 */
export function useScrollable(ref) {
  const [scrollable, setScrollable] = useState(false)
  // Content can change without the box changing size, so measure after every
  // render as well as on resize. setState with an unchanged value is a no-op.
  useEffect(() => {
    const node = ref.current
    if (!node) return undefined
    // Content that already holds a tab stop (links, buttons) is scrolled by
    // moving focus through it, so the box needs no stop of its own.
    const measure = () => setScrollable(
      (node.scrollHeight > node.clientHeight + 1 || node.scrollWidth > node.clientWidth + 1)
      && !node.querySelector(FOCUSABLE),
    )
    measure()
    if (typeof ResizeObserver !== 'function') return undefined
    const observer = new ResizeObserver(measure)
    observer.observe(node)
    for (const child of node.children) observer.observe(child)
    return () => observer.disconnect()
  })
  return scrollable
}

/**
 * A container that scrolls, reachable and scrollable from the keyboard.
 *
 * It always has an accessible name, because a focusable region without one is
 * announced as nothing. `axis` limits the scroll direction.
 */
export function FederationScrollRegion({
  label,
  'aria-label': ariaLabel,
  'aria-labelledby': labelledBy,
  role = 'region',
  axis = 'both',
  className,
  children,
  ...props
}) {
  const name = ariaLabel || label
  if (!name && !labelledBy) throw new Error('FederationScrollRegion requires label, aria-label or aria-labelledby')
  if (!['both', 'x', 'y'].includes(axis)) throw new Error('FederationScrollRegion axis must be one of: both, x, y')
  const ref = useRef(null)
  const scrollable = useScrollable(ref)
  return (
    <div
      ref={ref}
      role={role}
      aria-label={labelledBy ? undefined : name}
      aria-labelledby={labelledBy}
      tabIndex={scrollable ? 0 : undefined}
      data-axis={axis}
      data-scrollable={scrollable || undefined}
      className={cx('fd-scroll-region', className)}
      {...props}
    >
      {children}
    </div>
  )
}
