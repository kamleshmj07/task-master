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

/** Whole days from `from` to `to`, both `YYYY-MM-DD`. */
export function daysBetween(from: string, to: string): number {
  const [fy = 0, fm = 1, fd = 1] = from.split('-').map(Number)
  const [ty = 0, tm = 1, td = 1] = to.split('-').map(Number)
  return Math.round((Date.UTC(ty, tm - 1, td) - Date.UTC(fy, fm - 1, fd)) / 86_400_000)
}

/** "Due today", "Due tomorrow", "Overdue since Fri 20 Nov", "Due Sat 28 Nov". */
export function dueLabel(iso: string | null, today: string): string {
  if (iso === null) return 'No date'
  const delta = daysBetween(today, iso)
  if (delta === 0) return 'Due today'
  if (delta === 1) return 'Due tomorrow'
  if (delta < 0) return `Overdue since ${formatDay(iso)}`
  return `Due ${formatDay(iso)}`
}

export interface QuickDate {
  label: string
  date: string
}

/** One-tap postpone dates, counted from `today`. */
export function quickDates(today: string): QuickDate[] {
  return [
    { label: 'Tomorrow', date: addDays(today, 1) },
    { label: 'In 3 days', date: addDays(today, 3) },
    { label: 'Next week', date: addDays(today, 7) },
  ]
}

/** The browser's IANA timezone, e.g. "Asia/Kolkata". */
export function browserTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone
}

/** Every IANA timezone the browser knows, always including `current`. */
export function timezoneOptions(current: string): string[] {
  const zones = Intl.supportedValuesOf('timeZone')
  return zones.includes(current) ? zones : [current, ...zones]
}
