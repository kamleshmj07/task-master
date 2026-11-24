import type { ReactNode } from 'react'

import { EMPTY_ICONS } from '@/emptyStates'

interface EmptyStateProps {
  icon: keyof typeof EMPTY_ICONS
  title: string
  children: ReactNode
  actionLabel: string
  onAction: () => void
}

/** What a page is for, in a sentence, and one way to start. */
export function EmptyState({ icon, title, children, actionLabel, onAction }: EmptyStateProps) {
  return (
    <section className="panel empty-state" aria-label={title}>
      <span className="empty-state-icon" aria-hidden="true">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d={EMPTY_ICONS[icon]} />
        </svg>
      </span>
      <h2>{title}</h2>
      <p>{children}</p>
      <button type="button" className="primary" onClick={onAction}>
        {actionLabel}
      </button>
    </section>
  )
}
