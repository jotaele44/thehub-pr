import React, { useId } from 'react'
import { cx } from './util.js'

/**
 * A labelled single-line text input. The help and error texts are tied to
 * the input, so they are read with it; the error is announced when it
 * appears. `inputRef` reaches the input (the package supports React 18,
 * where a function component cannot take `ref`).
 */
export function FederationTextField({ label, help, error, id, inputRef, className, type = 'text', ...props }) {
  if (!label) throw new Error('FederationTextField requires label')
  const generated = useId()
  const inputId = id || `${generated}-input`
  const helpId = help ? `${generated}-help` : undefined
  const errorId = error ? `${generated}-error` : undefined
  return (
    <div className={cx('fd-field', className)} data-invalid={error ? true : undefined}>
      <label className="fd-field__label" htmlFor={inputId}>{label}</label>
      <input
        ref={inputRef}
        id={inputId}
        type={type}
        className="fd-field__input"
        aria-invalid={error ? true : undefined}
        aria-describedby={[helpId, errorId].filter(Boolean).join(' ') || undefined}
        {...props}
      />
      {help ? <p className="fd-field__help" id={helpId}>{help}</p> : null}
      {error ? <p className="fd-field__error" id={errorId} role="alert">{error}</p> : null}
    </div>
  )
}
