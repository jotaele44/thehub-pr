import React, { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { cx } from './util.js'

const EDGE = 8

/**
 * A button that opens a menu of actions.
 *
 * Keyboard: Enter, Space or ArrowDown opens on the first action and ArrowUp
 * on the last; the arrows move and wrap; Home and End jump; a letter jumps to
 * the next action starting with it; Escape closes; Tab closes and moves on.
 * Choosing an action, or closing with Escape, returns focus to the button.
 * A click outside closes without moving focus.
 *
 * `items` is `[{ id, label, onSelect?, disabled?, destructive? }]`. The same
 * list can feed a toolbar or a context menu; this component only draws it.
 */
export function FederationMenu({
  label,
  'aria-label': ariaLabel,
  items = [],
  onSelect,
  align = 'start',
  triggerClassName = 'fd-button fd-button--secondary',
  className,
  children,
  ...props
}) {
  if (!label && !ariaLabel) throw new Error('FederationMenu requires label or aria-label')
  const menuId = useId()
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)
  const triggerRef = useRef(null)
  const listRef = useRef(null)
  // Which action takes focus when the menu opens: 'first' or 'last'.
  const entryRef = useRef('first')

  const enabled = useCallback(() => [...(listRef.current?.querySelectorAll('[role="menuitem"]:not([aria-disabled="true"])') || [])], [])
  const close = useCallback((returnFocus) => {
    setOpen(false)
    if (returnFocus) triggerRef.current?.focus()
  }, [])

  // Fixed positioning keeps the menu out of any scrolling or clipping
  // ancestor (a sidebar, a table). It flips above the button and is pulled
  // inside the viewport when it would not fit.
  const place = useCallback(() => {
    const list = listRef.current
    const trigger = triggerRef.current
    if (!list || !trigger) return
    const anchor = trigger.getBoundingClientRect()
    const width = list.offsetWidth
    const height = list.offsetHeight
    let top = anchor.bottom + 4
    if (top + height > window.innerHeight - EDGE) top = Math.max(EDGE, anchor.top - 4 - height)
    let left = align === 'end' ? anchor.right - width : anchor.left
    left = Math.max(EDGE, Math.min(left, window.innerWidth - width - EDGE))
    list.style.top = `${top}px`
    list.style.left = `${left}px`
  }, [align])

  useLayoutEffect(() => {
    if (!open) return
    place()
    const targets = enabled()
    // Moving focus must not scroll the page out from under the menu.
    ;(entryRef.current === 'last' ? targets[targets.length - 1] : targets[0])?.focus({ preventScroll: true })
  }, [open, place, enabled])

  // The menu follows its button when the page scrolls or is resized; closing
  // it instead would close it on the scroll that moving focus can cause.
  useEffect(() => {
    if (!open) return undefined
    const outside = (event) => { if (!rootRef.current?.contains(event.target)) close(false) }
    document.addEventListener('pointerdown', outside, true)
    window.addEventListener('resize', place)
    window.addEventListener('scroll', place, true)
    return () => {
      document.removeEventListener('pointerdown', outside, true)
      window.removeEventListener('resize', place)
      window.removeEventListener('scroll', place, true)
    }
  }, [open, close, place])

  const openWith = (entry) => {
    entryRef.current = entry
    setOpen(true)
  }
  const onTriggerKeyDown = (event) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      openWith(event.key === 'ArrowUp' ? 'last' : 'first')
    }
  }
  const onMenuKeyDown = (event) => {
    const targets = enabled()
    const index = targets.indexOf(document.activeElement)
    const move = (next) => {
      event.preventDefault()
      targets[(next + targets.length) % targets.length]?.focus()
    }
    if (event.key === 'ArrowDown') move(index + 1)
    else if (event.key === 'ArrowUp') move(index <= 0 ? targets.length - 1 : index - 1)
    else if (event.key === 'Home') move(0)
    else if (event.key === 'End') move(targets.length - 1)
    else if (event.key === 'Escape') {
      // Handled here so a dialog around the menu does not close as well.
      event.preventDefault()
      event.stopPropagation()
      close(true)
    } else if (event.key === 'Tab') {
      close(false)
    } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey && event.key !== ' ') {
      const letter = event.key.toLowerCase()
      const ordered = [...targets.slice(index + 1), ...targets.slice(0, index + 1)]
      ordered.find((node) => node.textContent.trim().toLowerCase().startsWith(letter))?.focus()
    }
  }
  const choose = (item) => {
    if (item.disabled) return
    close(true)
    item.onSelect?.(item)
    onSelect?.(item)
  }

  return (
    <span ref={rootRef} className={cx('fd-menu', className)} {...props}>
      <button
        ref={triggerRef}
        type="button"
        className={cx(triggerClassName, 'fd-focus', 'fd-menu__trigger')}
        aria-label={ariaLabel}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => (open ? close(false) : openWith('first'))}
        onKeyDown={onTriggerKeyDown}
      >
        {children ?? label}
      </button>
      {open ? (
        <ul ref={listRef} id={menuId} className="fd-menu__list" role="menu" aria-label={ariaLabel || (typeof label === 'string' ? label : undefined)} onKeyDown={onMenuKeyDown}>
          {items.map((item) => (
            <li key={item.id} role="none">
              <button
                type="button"
                role="menuitem"
                tabIndex={-1}
                className="fd-menu__item"
                aria-disabled={item.disabled ? true : undefined}
                data-destructive={item.destructive || undefined}
                data-menu-item-id={item.id}
                onClick={() => choose(item)}
              >
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </span>
  )
}

/**
 * The "…" menu on one item of a list. Its name says which item it acts on,
 * so a row of them is not a row of identical "More" buttons.
 */
export function FederationItemMenu({ itemLabel, label, items, className, ...props }) {
  if (typeof itemLabel !== 'string' || itemLabel.trim() === '') throw new Error('FederationItemMenu requires itemLabel: the name of the item it acts on')
  return (
    <FederationMenu
      aria-label={label || `Actions for ${itemLabel}`}
      items={items}
      align="end"
      triggerClassName="fd-icon-button"
      className={cx('fd-item-menu', className)}
      {...props}
    >
      <svg className="fd-item-menu__glyph" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false"><circle cx="5" cy="12" r="2" /><circle cx="12" cy="12" r="2" /><circle cx="19" cy="12" r="2" /></svg>
    </FederationMenu>
  )
}
