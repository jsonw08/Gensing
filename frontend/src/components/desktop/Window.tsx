import type { ReactNode } from 'react'

// A desktop window: pinstriped title bar, grey face, and a body. Windows sit in a fixed layout
// (no dragging); `className` places them. `toolbar` sits between the title bar and the body,
// `footer` under the body (buttons, status line).
export function Window({
  title,
  className,
  toolbar,
  footer,
  bodyClassName,
  children,
  labelledBy,
}: {
  title: string
  className?: string
  toolbar?: ReactNode
  footer?: ReactNode
  bodyClassName?: string
  children: ReactNode
  labelledBy?: string
}) {
  const titleId = labelledBy ?? `win-${title.replace(/\W+/g, '-').toLowerCase()}`
  return (
    <section className={`window${className ? ` ${className}` : ''}`} aria-labelledby={titleId}>
      <header className="titlebar">
        <span className="closebox" aria-hidden="true" />
        <h2 id={titleId} className="titlebar-text">
          {title}
        </h2>
      </header>
      {toolbar && <div className="window-toolbar">{toolbar}</div>}
      <div className={`window-body${bodyClassName ? ` ${bodyClassName}` : ''}`}>{children}</div>
      {footer && <footer className="window-footer">{footer}</footer>}
    </section>
  )
}

/** A small dialog box (alert / progress) drawn inside a window or over the desktop. */
export function DialogBox({
  icon,
  children,
  actions,
  role = 'status',
}: {
  icon?: ReactNode
  children: ReactNode
  actions?: ReactNode
  role?: 'status' | 'alert' | 'dialog'
}) {
  return (
    <div className="dialog" role={role}>
      <div className="dialog-main">
        {icon && <div className="dialog-icon">{icon}</div>}
        <div className="dialog-text">{children}</div>
      </div>
      {actions && <div className="dialog-actions">{actions}</div>}
    </div>
  )
}

/** Indeterminate "barber pole" progress bar. */
export function Progress({ label }: { label: string }) {
  return <div className="progress" role="progressbar" aria-label={label} aria-busy="true" />
}
