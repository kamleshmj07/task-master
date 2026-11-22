import type {
  GoalRead,
  PostponeReason,
  RoutineRead,
} from '@task-master/api-client'

import { api } from '@/api'
import { WEEKDAYS } from '@/dates'

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
