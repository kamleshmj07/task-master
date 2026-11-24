/** Icons for the empty states, as stroke paths on a 24px grid. */
export const EMPTY_ICONS = {
  tasks: 'M4 7h3M4 12h3M4 17h3M10 7h10M10 12h10M10 17h6',
  goals: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 4a5 5 0 1 0 0 10 5 5 0 0 0 0-10Zm0 4.5a.5.5 0 1 0 0 1 .5.5 0 0 0 0-1Z',
  routines: 'M21 12a9 9 0 1 1-3-6.7L21 8M21 3v5h-5',
} as const

/** Put the cursor in the first field of the form under `headingId`. */
export function focusFormUnder(headingId: string): void {
  const field = document.getElementById(headingId)?.closest('section')?.querySelector<HTMLElement>('input, select, textarea')
  if (typeof field?.scrollIntoView === 'function') field.scrollIntoView({ block: 'center', behavior: 'smooth' })
  field?.focus({ preventScroll: true })
}
