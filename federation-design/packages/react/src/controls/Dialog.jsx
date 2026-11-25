import React, { useCallback, useEffect, useId, useRef } from 'react'
import { cx } from './util.js'

/**
 * A modal dialog on the native <dialog> element.
 *
 * The browser traps focus and makes the rest of the page inert; Escape and a
 * click on the backdrop ask to close. Focus goes to the element marked
 * `data-autofocus` (or where the browser puts it) and returns to whatever
 * opened the dialog, however it was closed.
 *
 * Controlled: `open` decides whether it is shown and `onClose` is called
 * when the person asks to close it. `dismissible={false}` keeps Escape and
 * the backdrop from closing it while work is in flight.
 */
export function FederationDialog({
  open = false,
  onClose,
  title,
  description,
  footer,
  closeLabel = 'Close',
  dismissible = true,
  className,
  children,
  ...props
}) {
  if (!title) throw new Error('FederationDialog requires a title')
  const titleId = useId()
  const descriptionId = useId()
  const dialogRef = useRef(null)
  const openerRef = useRef(null)
  const openRef = useRef(open)
  openRef.current = open

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (open && !dialog.open) {
      openerRef.current = document.activeElement
      if (typeof dialog.showModal === 'function') dialog.showModal()
      else dialog.setAttribute('open', '')
      const target = dialog.querySelector('[data-autofocus]')
      target?.focus?.()
      target?.select?.()
    } else if (!open && dialog.open) {
      if (typeof dialog.close === 'function') dialog.close()
      else dialog.removeAttribute('open')
    }
  }, [open])

  // Fires for Escape as well as for close(). If `open` is still true the
  // person closed it and the host has to be told.
  const handleClose = useCallback(() => {
    // The event is delivered after close() returns. If the dialog has been
    // opened again by then, this event belongs to the earlier closing and
    // must neither close the new one nor move focus out of it.
    if (dialogRef.current?.open) return
    const opener = openerRef.current
    openerRef.current = null
    // The close event arrives a moment after the dialog closed. Only put
    // focus back if nothing else has taken it since; never pull it away from
    // where the person has already gone.
    const active = document.activeElement
    const adrift = !active || active === document.body || dialogRef.current?.contains(active)
    if (adrift && opener?.isConnected) opener.focus?.()
    if (openRef.current) onClose?.()
  }, [onClose])
  const handleCancel = useCallback((event) => {
    if (!dismissible) event.preventDefault()
  }, [dismissible])

  return (
    <dialog
      ref={dialogRef}
      className={cx('fd-dialog', className)}
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      onClose={handleClose}
      onCancel={handleCancel}
      onClick={(event) => { if (dismissible && event.target === event.currentTarget) onClose?.() }}
      {...props}
    >
      <div className="fd-dialog__surface">
        <div className="fd-dialog__header">
          <h2 className="fd-dialog__title" id={titleId}>{title}</h2>
          {closeLabel ? <button type="button" className="fd-dialog__close" disabled={!dismissible} onClick={() => onClose?.()}>{closeLabel}</button> : null}
        </div>
        {description ? <p className="fd-dialog__description" id={descriptionId}>{description}</p> : null}
        {children ? <div className="fd-dialog__body">{children}</div> : null}
        {footer ? <div className="fd-dialog__footer">{footer}</div> : null}
      </div>
    </dialog>
  )
}
