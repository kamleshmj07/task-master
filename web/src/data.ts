import type {
  GoalRead,
  PostponeReason,
  RoutineRead,
  TaskRead,
} from '@task-master/api-client'

import { api } from '@/api'
import { daysBetween, WEEKDAYS } from '@/dates'

export const REASONS: { value: PostponeReason; label: string }[] = [
  { value: 'stuck', label: "I don't know where to start" },
  { value: 'dreading', label: "I don't want to do it" },
  { value: 'blocked', label: "Something's in the way" },
  { value: 'other', label: 'Other…' },
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

export const TIME_LIMITS = [15, 30, 45, 60, 90, 120, 240] as const

/** "45 min" or "1.5 hours"; empty when there is no limit. */
export function timeLimitLabel(minutes: number | null | undefined): string {
  if (!minutes) return ''
  if (minutes < 60) return `${minutes} min`
  const hours = minutes / 60
  return `${hours} ${hours === 1 ? 'hour' : 'hours'}`
}

export interface TaskGroup {
  id: 'overdue' | 'today' | 'week' | 'later'
  label: string
  tasks: TaskRead[]
}

/** Dated tasks split into Overdue, Today, This week and Later, soonest first. */
export function groupScheduled(tasks: TaskRead[], today: string): TaskGroup[] {
  const dated = tasks
    .filter((task): task is TaskRead & { due_date: string } => task.due_date !== null)
    .sort((a, b) => a.due_date.localeCompare(b.due_date))
  const groups: TaskGroup[] = [
    { id: 'overdue', label: 'Overdue', tasks: [] },
    { id: 'today', label: 'Today', tasks: [] },
    { id: 'week', label: 'This week', tasks: [] },
    { id: 'later', label: 'Later', tasks: [] },
  ]
  for (const task of dated) {
    const delta = daysBetween(today, task.due_date)
    const index = delta < 0 ? 0 : delta === 0 ? 1 : delta <= 7 ? 2 : 3
    groups[index]?.tasks.push(task)
  }
  return groups.filter((group) => group.tasks.length > 0)
}
