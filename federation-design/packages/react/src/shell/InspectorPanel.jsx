import React, { useCallback, useEffect, useId, useRef } from 'react'
import { FEDERATION_SHELL_BREAKPOINTS } from './nav.js'
import { cx } from './parts.jsx'

/**
 * The detail panel for a selected record.
 *
 * One <dialog>, two presentations. At the desktop breakpoint and above it is
 * opened non-modally and sits in the shell's inspector column, beside main,
 * without taking focus from the control that opened it. Below that it is
 * opened modally as a drawer, which traps focus and closes on Escape. The
 * presentation follows the viewport while open, and the panel's children are
 * never remounted by the switch.
 *
 * Controlled: `open` decides whether it is shown, and `onClose` is called
 * when the person asks to close it (the close button, Escape, the backdrop).
 */
export function FederationInspectorPanel({
  open = false,
  onClose,
  title,
  closeLabel = 'Close inspector',
  className,
  children,
  ...props
}) {
  if (!title) throw new Error('FederationInspectorPanel requires a title')
  const titleId = useId()
  const dialogRef = useRef(null)
  const openerRef = useRef(null)
  const openRef = useRef(open)
  openRef.current = open

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return undefined
    const desktop = typeof window.matchMedia === 'function'
      ? window.matchMedia(`(min-width: ${FEDERATION_SHELL_BREAKPOINTS.desktop}px)`)
      : null
    const present = () => {
      if (dialog.open && typeof dialog.close === 'function') dialog.close()
      if (!openRef.current) return
      if (desktop && !desktop.matches && typeof dialog.showModal === 'function') {
        dialog.showModal()
      } else if (typeof dialog.show === 'function') {
        dialog.show()
        // show() moves focus into the panel. Docked, it is a side panel, not
        // an interruption: leave focus where the person was working.
        openerRef.current?.focus?.()
      } else {
        dialog.setAttribute('open', '')
      }
    }
    if (open && !dialog.open) openerRef.current = document.activeElement
    present()
    if (!open && openerRef.current) {
      const opener = openerRef.current
      openerRef.current = null
      if (dialog.contains(document.activeElement) || document.activeElement === document.body) opener.focus?.()
    }
    desktop?.addEventListener?.('change', present)
    return () => desktop?.removeEventListener?.('change', present)
  }, [open])

  // The close event is delivered after close() returns. If the dialog is open
  // again by then, it was only switching presentation; if `open` is already
  // false, the host closed it. Otherwise the person did (Escape in a drawer).
  const handleClose = useCallback(() => {
    if (dialogRef.current?.open || !openRef.current) return
    onClose?.()
  }, [onClose])
  // A non-modal dialog does not close on Escape by itself.
  const handleKeyDown = useCallback((event) => {
    if (event.key === 'Escape' && !event.defaultPrevented && !dialogRef.current?.matches?.(':modal')) {
      event.stopPropagation()
      onClose?.()
    }
  }, [onClose])

  return (
    <dialog
      ref={dialogRef}
      className={cx('fd-inspector', className)}
      aria-labelledby={titleId}
      onClose={handleClose}
      onKeyDown={handleKeyDown}
      onClick={(event) => { if (event.target === event.currentTarget) onClose?.() }}
      {...props}
    >
      <div className="fd-inspector__header">
        <h2 className="fd-inspector__title" id={titleId}>{title}</h2>
        <button type="button" className="fd-inspector__close" onClick={() => onClose?.()}>{closeLabel}</button>
      </div>
      <div className="fd-inspector__body">{children}</div>
    </dialog>
  )
}
