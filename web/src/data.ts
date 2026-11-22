import type {
  GoalRead,
  PostponeReason,
  RoutineRead,
  TaskRead,
} from '@task-master/api-client'

import { api } from '@/api'
import { daysBetween, WEEKDAYS } from '@/dates'

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
export function describeSchedule(routine: RoutineRead): string {
  switch (routine.frequency) {
    case 'daily':
      return 'Every day'
    case 'weekly':
      return (routine.weekdays ?? []).map((day) => WEEKDAYS[day]).join(', ')
    case 'monthly':
      return `Monthly on day ${routine.day_of_month ?? '?'} (or the last day)`
  }
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
