import React from 'react'
import { FEDERATION_PRESENTATION_TONES } from '../semantics.js'
import { cx } from './util.js'

const KINDS = ['dot', 'spinner', 'alert']

/**
 * A small status mark beside an item: a dot, a spinner or an alert.
 *
 * Colour and shape are never the only signal. `label` is required and is the
 * mark's text equivalent: announced as the mark's name, or shown beside it
 * with `showLabel`.
 */
export function FederationStatusMark({ kind = 'dot', tone = 'neutral', label, showLabel = false, className, ...props }) {
  if (typeof label !== 'string' || label.trim() === '') throw new Error('FederationStatusMark requires label: the status in words')
  if (!KINDS.includes(kind)) throw new Error(`FederationStatusMark kind must be one of: ${KINDS.join(', ')}`)
  if (!FEDERATION_PRESENTATION_TONES.includes(tone)) throw new Error(`FederationStatusMark tone must be one of: ${FEDERATION_PRESENTATION_TONES.join(', ')}`)
  const glyph = <span className="fd-status-mark__glyph" aria-hidden="true">{kind === 'alert' ? '!' : null}</span>
  return showLabel ? (
    <span className={cx('fd-status-mark', className)} data-kind={kind} data-tone={tone} {...props}>
      {glyph}
      <span className="fd-status-mark__label">{label}</span>
    </span>
  ) : (
    <span className={cx('fd-status-mark', className)} data-kind={kind} data-tone={tone} role="img" aria-label={label} {...props}>
      {glyph}
    </span>
  )
}
