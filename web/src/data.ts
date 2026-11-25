import type {
  DayMark,
  GoalColor,
  GoalRead,
  PostponeReason,
  RoutineFrequency,
  RoutineRead,
  TaskRead,
  TaskRepeat,
} from '@task-master/api-client'

import { api } from '@/api'
import { daysBetween, formatDay, WEEKDAYS } from '@/dates'

export interface ReasonOption {
  value: PostponeReason
  label: string
  /** What the reason means, in a few words. */
  hint: string
  /** What the app will suggest for it. */
  fix: string
}

export const REASONS: ReasonOption[] = [
  {
    value: 'stuck',
    label: "I don't know where to start",
    hint: 'Unclear, or too big',
    fix: "We'll help you shrink the first step",
  },
  {
    value: 'dreading',
    label: "I don't want to do it",
    hint: 'Boring, stressful or dreaded',
    fix: "We'll help you lower the bar to start",
  },
  {
    value: 'blocked',
    label: "Something's in the way",
    hint: 'Waiting on someone, or no time',
    fix: "We'll help you make the blocker explicit",
  },
  {
    value: 'other',
    label: 'Other…',
    hint: 'Tell us in your own words',
    fix: "We'll help you replan",
  },
]

export async function loadGoals(): Promise<GoalRead[]> {
  const { data } = await api.GET('/goals', {
    params: { query: { status: 'active', limit: 100 } },
  })
  return data ?? []
}

/** Human summary of a routine's schedule, e.g. "Mon, Wed, Fri". */
export function describeSchedule(routine: Pick<RoutineRead, 'frequency' | 'weekdays' | 'day_of_month'>): string {
  switch (routine.frequency) {
    case 'daily':
      return 'Every day'
    case 'weekly':
      return (routine.weekdays ?? []).map((day) => WEEKDAYS[day]).join(', ')
    case 'monthly':
      return `Monthly on day ${routine.day_of_month ?? '?'} (or the last day)`
  }
}

/** "Repeats every day" or "Repeats Mon, Thu, until 1 Mar 2027". */
export function describeRepeat(repeat: TaskRepeat): string {
  const when =
    repeat.frequency === 'daily'
      ? 'every day'
      : repeat.frequency === 'weekly'
        ? (repeat.weekdays ?? []).map((day) => WEEKDAYS[day]).join(', ')
        : `monthly on day ${repeat.day_of_month ?? '?'}`
  return `Repeats ${when}${repeat.until ? `, until ${formatDay(repeat.until)}` : ''}`
}

export type RepeatChoice = 'none' | RoutineFrequency

/** The repeat fields of a task form, as the user is editing them. */
export interface RepeatDraft {
  frequency: RepeatChoice
  weekdays: number[]
  dayOfMonth: string
  until: string
}

export function repeatDraft(repeat: TaskRepeat | null | undefined): RepeatDraft {
  return {
    frequency: repeat?.frequency ?? 'none',
    weekdays: repeat?.weekdays ?? [],
    dayOfMonth: repeat?.day_of_month ? String(repeat.day_of_month) : '',
    until: repeat?.until ?? '',
  }
}

/** The rule to send to the API; null for a task that does not repeat. */
export function repeatFromDraft(draft: RepeatDraft): TaskRepeat | null {
  if (draft.frequency === 'none') return null
  return {
    frequency: draft.frequency,
    weekdays: draft.frequency === 'weekly' ? [...draft.weekdays].sort((a, b) => a - b) : null,
    day_of_month: draft.frequency === 'monthly' ? Number(draft.dayOfMonth) : null,
    until: draft.until || null,
  }
}

/** Weekday of an ISO date, 0 = Monday ... 6 = Sunday, as the API counts. */
export function weekdayOf(iso: string): number {
  return (new Date(`${iso}T00:00:00`).getDay() + 6) % 7
}

/** "45 min" or "1.5 hours"; empty when there is no limit. */
export function timeLimitLabel(minutes: number | null | undefined): string {
  if (!minutes) return ''
  if (minutes < 60) return `${minutes} min`
  const hours = minutes / 60
  return `${hours} ${hours === 1 ? 'hour' : 'hours'}`
}

export interface TaskGroup {
  id: 'today' | 'week' | 'later' | 'ready' | 'overdue' | 'someday' | 'done'
  label: string
  tasks: TaskRead[]
}

function byDueDate(a: TaskRead, b: TaskRead): number {
  return (a.due_date ?? '9999').localeCompare(b.due_date ?? '9999')
}

/** Scheduled tasks split into Today, This week and Later, soonest first. */
export function groupScheduled(tasks: TaskRead[], today: string): TaskGroup[] {
  const groups: TaskGroup[] = [
    { id: 'today', label: 'Today', tasks: [] },
    { id: 'week', label: 'This week', tasks: [] },
    { id: 'later', label: 'Later', tasks: [] },
  ]
  for (const task of [...tasks].sort(byDueDate)) {
    if (task.due_date === null) continue
    const delta = daysBetween(today, task.due_date)
    groups[delta <= 0 ? 0 : delta <= 7 ? 1 : 2]?.tasks.push(task)
  }
  return groups.filter((group) => group.tasks.length > 0)
}

/** Review tasks: every step done first, then the overdue ones. */
export function groupReview(tasks: TaskRead[]): TaskGroup[] {
  const ready = tasks.filter((task) => task.next_step === null)
  const overdue = tasks.filter((task) => task.next_step !== null).sort(byDueDate)
  return [
    { id: 'ready' as const, label: 'Ready to complete', tasks: ready },
    { id: 'overdue' as const, label: 'Overdue', tasks: overdue },
  ].filter((group) => group.tasks.length > 0)
}

export type TimeUnit = 'min' | 'hours'

/** The API's limit: 24 hours. */
export const MAX_MINUTES = 1440

/** Minutes for `amount` of `unit`, or null when the field is empty. */
export function toMinutes(amount: string, unit: TimeUnit): number | null {
  const value = Number(amount)
  if (!amount.trim() || !Number.isFinite(value) || value <= 0) return null
  return Math.round(unit === 'hours' ? value * 60 : value)
}

/** "1 task", "3 tasks". */
export function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? '' : 's'}`
}

/** Days after which an untouched active goal counts as quiet (matches notifications). */
export const QUIET_GOAL_DAYS = 30
/** Deadlines this close are flagged (matches notifications). */
export const URGENT_DEADLINE_DAYS = 7

export interface GoalHealth {
  deadline: string | null
  deadlineUrgent: boolean
  quiet: string | null
}

/** Plain-language deadline and movement facts for a goal card. */
export function goalHealth(goal: GoalRead, today: string): GoalHealth {
  let deadline: string | null = null
  let deadlineUrgent = false
  if (goal.deadline) {
    const left = daysBetween(today, goal.deadline)
    const day = formatDay(goal.deadline)
    deadline =
      left < 0
        ? `Deadline passed on ${day}`
        : left === 0
          ? 'Deadline is today'
          : `Deadline ${day}, ${plural(left, 'day')} left`
    deadlineUrgent = goal.status === 'active' && left <= URGENT_DEADLINE_DAYS
  }
  const quietDays = daysBetween(goal.progress.last_moved_at.slice(0, 10), today)
  const quiet = goal.status === 'active' && quietDays >= QUIET_GOAL_DAYS ? `Quiet for ${quietDays} days` : null
  return { deadline, deadlineUrgent, quiet }
}

/** Goal colours in palette order, as the picker offers them. */
export const GOAL_COLORS: { value: GoalColor; label: string }[] = [
  { value: 'sky', label: 'Sky' },
  { value: 'periwinkle', label: 'Periwinkle' },
  { value: 'lilac', label: 'Lilac' },
  { value: 'mauve', label: 'Mauve' },
  { value: 'steel', label: 'Steel' },
  { value: 'aqua', label: 'Aqua' },
]

/** Look up goals by id, for showing a task's goal. */
export function goalsById(goals: GoalRead[] | null | undefined): Map<string, GoalRead> {
  return new Map((goals ?? []).map((goal) => [goal.id, goal]))
}

/** How a routine's last seven days read aloud, e.g. "done 4 of 5 days it was due". */
export function weekSummary(days: DayMark[]): string {
  const due = days.filter((day) => day !== 'not_due').length
  const done = days.filter((day) => day === 'done').length
  return due === 0 ? 'Last 7 days: not due' : `Last 7 days: done ${done} of ${plural(due, 'day')} it was due`
}

/** Short reason names for summaries, e.g. "2 blocked". */
export const REASON_NAMES: Record<PostponeReason, string> = {
  stuck: 'stuck',
  dreading: 'dreading',
  blocked: 'blocked',
  other: 'other',
}

/** "Postponed 3 times: 2 blocked, 1 dreading"; empty when never postponed. */
export function postponementSummary(count: number, reasons: Partial<Record<PostponeReason, number>>): string {
  if (count === 0) return ''
  const parts = REASONS.map(({ value }) => [value, reasons[value] ?? 0] as const)
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([value, n]) => `${n} ${REASON_NAMES[value]}`)
  const head = `Postponed ${plural(count, 'time')}`
  return parts.length ? `${head}: ${parts.join(', ')}` : head
}

/** Split stored minutes back into an amount and a unit for editing. */
export function fromMinutes(minutes: number | null): { amount: string; unit: TimeUnit } {
  if (!minutes) return { amount: '', unit: 'min' }
  // Whole quarter-hours from an hour up read better as hours: 90 → 1.5 hours.
  return minutes >= 60 && minutes % 15 === 0
    ? { amount: String(minutes / 60), unit: 'hours' }
    : { amount: String(minutes), unit: 'min' }
}
