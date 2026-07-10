import React from 'react'

function cx(...values) {
  return values.filter(Boolean).join(' ')
}

export function FederationButton({ variant = 'primary', className, type = 'button', ...props }) {
  return <button type={type} className={cx('fd-button', `fd-button--${variant}`, 'fd-focus', className)} {...props} />
}

export function FederationPanel({ as: Component = 'section', className, ...props }) {
  return <Component className={cx('fd-panel', className)} {...props} />
}

export function FederationStatusBadge({ status, children, className, ...props }) {
  const normalized = String(status || 'offline').toLowerCase()
  return (
    <span className={cx('fd-status', `fd-status--${normalized}`, className)} data-status={normalized} {...props}>
      {children ?? normalized}
    </span>
  )
}

export function FederationEmptyState({ title, description, action, className, ...props }) {
  return (
    <div className={cx('fd-empty-state', className)} role="status" {...props}>
      <h2 className="fd-empty-state__title">{title}</h2>
      {description ? <p className="fd-empty-state__description">{description}</p> : null}
      {action ? <div className="fd-empty-state__action">{action}</div> : null}
    </div>
  )
}
