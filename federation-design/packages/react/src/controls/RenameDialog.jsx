import React, { useState } from 'react'
import { FederationDialog } from './Dialog.jsx'
import { FederationTextField } from './TextField.jsx'

// Mounted only while the dialog is open, so every opening starts from the
// current name (not from an abandoned edit) and the field already holds it
// when the dialog moves focus there and selects it.
function RenameForm({ currentName, onRename, onClose, onSavingChange, label, maxLength, saveLabel, cancelLabel, emptyMessage, tooLongMessage, failedMessage, validate }) {
  const [value, setValue] = useState(currentName)
  const [error, setError] = useState(null)
  const [saving, setSavingState] = useState(false)
  const setSaving = (next) => {
    setSavingState(next)
    onSavingChange(next)
  }

  const name = value.trim()
  const problem = name === ''
    ? emptyMessage
    : name.length > maxLength
      ? (tooLongMessage || `Use ${maxLength} characters or fewer.`)
      : (validate?.(name) || null)
  const unchanged = name === currentName.trim()

  const submit = async (event) => {
    event.preventDefault()
    if (saving) return
    if (problem) {
      setError(problem)
      return
    }
    if (unchanged) return
    setSaving(true)
    setError(null)
    try {
      await onRename(name)
    } catch (failure) {
      setSaving(false)
      setError((failure && failure.message) || failedMessage)
      return
    }
    setSaving(false)
    onClose?.()
  }

  return (
    <form className="fd-rename-dialog__form" onSubmit={submit} noValidate>
      <FederationTextField
        label={label}
        value={value}
        error={error}
        autoComplete="off"
        data-autofocus=""
        onChange={(event) => {
          setValue(event.target.value)
          if (error) setError(null)
        }}
      />
      <div className="fd-dialog__footer">
        <button type="button" className="fd-button fd-button--secondary fd-focus" disabled={saving} onClick={() => onClose?.()}>{cancelLabel}</button>
        <button type="submit" className="fd-button fd-button--primary fd-focus" disabled={saving || unchanged} aria-busy={saving || undefined}>{saveLabel}</button>
      </div>
    </form>
  )
}

/**
 * Rename something the person named: a title, one line of guidance, the
 * current name prefilled and selected, Cancel and Save.
 *
 * The dialog validates and reports; it stores nothing. `onRename(name)` does
 * the write and may return a promise. If it throws or rejects, the message is
 * shown and the dialog stays open with what was typed. Names are trimmed; an
 * empty name, a name over `maxLength` and an unchanged name cannot be saved.
 *
 * Only for objects whose name the person owns. A record's identity or an
 * evidence citation is not renamed here.
 */
export function FederationRenameDialog({
  open = false,
  onClose,
  onRename,
  currentName = '',
  title = 'Rename',
  description,
  label = 'Name',
  maxLength = 120,
  saveLabel = 'Save',
  cancelLabel = 'Cancel',
  emptyMessage = 'Enter a name.',
  tooLongMessage,
  failedMessage = 'The name could not be saved.',
  validate,
  className,
  ...props
}) {
  if (typeof onRename !== 'function') throw new Error('FederationRenameDialog requires onRename')
  // While a save is in flight, Escape and the backdrop do not close the dialog.
  const [saving, setSaving] = useState(false)
  return (
    <FederationDialog
      open={open}
      onClose={onClose}
      title={title}
      description={description}
      closeLabel={null}
      dismissible={!saving}
      className={['fd-rename-dialog', className].filter(Boolean).join(' ')}
      {...props}
    >
      {open ? (
        <RenameForm
          currentName={currentName}
          onRename={onRename}
          onClose={onClose}
          onSavingChange={setSaving}
          label={label}
          maxLength={maxLength}
          saveLabel={saveLabel}
          cancelLabel={cancelLabel}
          emptyMessage={emptyMessage}
          tooLongMessage={tooLongMessage}
          failedMessage={failedMessage}
          validate={validate}
        />
      ) : null}
    </FederationDialog>
  )
}
