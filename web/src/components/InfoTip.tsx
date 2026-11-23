import { type ReactNode, useEffect, useId, useRef, useState } from 'react'

interface InfoTipProps {
  /** What the info is about, e.g. "Time limit"; names the button. */
  label: string
  children: ReactNode
}

/** An ⓘ button that shows a short explanation on click; Escape or a click away hides it. */
export function InfoTip({ label, children }: InfoTipProps) {
  const [open, setOpen] = useState(false)
  const id = useId()
  const ref = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (!open) return
    const handleClick = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  return (
    <span
      className="info"
      ref={ref}
      onKeyDown={(event) => {
        if (event.key === 'Escape') setOpen(false)
      }}
    >
      <button
        type="button"
        className="info-button"
        aria-label={`About ${label}`}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(!open)}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <circle cx="12" cy="12" r="9" />
          <path d="M12 11v5" />
          <path d="M12 8h.01" />
        </svg>
      </button>
      {open && (
        <span id={id} role="note" className="info-pop">
          {children}
        </span>
      )}
    </span>
  )
}
