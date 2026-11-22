/** `YYYY-MM-DD` for a date in the browser's local timezone. */
export function isoDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

export function todayIso(): string {
  return isoDate(new Date())
}

export function addDays(iso: string, days: number): string {
  const [year = 0, month = 1, day = 1] = iso.split('-').map(Number)
  return isoDate(new Date(year, month - 1, day + days))
}

/** "Sun 22 Nov" style label for an ISO date. */
export function formatDay(iso: string): string {
  const [year = 0, month = 1, day = 1] = iso.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString(undefined, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as const
