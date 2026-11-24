import type { HeadsUpItem, PlanSuggestion, TaskRead } from '@task-master/api-client'

import { describeRepeat, plural, timeLimitLabel } from '@/data'
import { daysBetween, formatDay } from '@/dates'

/** "Good morning, Ada"; the name is left out until the user has given one. */
export function greeting(now: Date, name: string | null | undefined): string {
  const hour = now.getHours()
  const part = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
  return name ? `${part}, ${name}` : part
}

/** "Tuesday 24 November", spelled out for the page heading. */
export function longDay(iso: string): string {
  const [year = 0, month = 1, day = 1] = iso.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString(undefined, {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })
}

/** Labels for the three slots, most important first. */
export const SLOT_LABELS = ['Most important', 'Next', 'If there is time'] as const

export function stepsDone(task: TaskRead): number {
  return task.steps.filter((step) => step.done).length
}

/** Why a task is suggested, in a few words. */
export function suggestionReason(suggestion: PlanSuggestion, today: string): string {
  const { task } = suggestion
  switch (suggestion.kind) {
    case 'left_over':
      return `Was number ${suggestion.previous_rank ?? '?'} yesterday, ${stepsDone(task)} of ${plural(task.steps.length, 'step')} done`
    case 'overdue':
      return overdueBy(task, today)
    case 'due_today': {
      if (task.repeat) return `Today's run, ${describeRepeat(task.repeat).toLowerCase()}`
      const limit = timeLimitLabel(task.time_limit_minutes)
      return limit ? `Due today, ${limit} limit` : 'Due today'
    }
    case 'goal_next':
      return `Next for ${suggestion.goal_title ?? 'a goal'}`
  }
}

/** What needs deciding about a heads-up task. */
export function headsUpReason(item: HeadsUpItem, today: string): string {
  switch (item.kind) {
    case 'overdue':
      return overdueBy(item.task, today)
    case 'ready':
      return 'Every step done'
    case 'due_soon': {
      const delta = daysBetween(today, item.task.due_date ?? today)
      if (delta === 0) return 'Due today'
      if (delta === 1) return 'Due tomorrow'
      return `Due ${formatDay(item.task.due_date ?? today)}`
    }
  }
}

function overdueBy(task: TaskRead, today: string): string {
  const days = daysBetween(task.due_date ?? today, today)
  return `Overdue by ${plural(days, 'day')}`
}

/** "Done at 9:40", in the user's clock. */
export function doneAt(task: TaskRead): string {
  if (!task.completed_at) return 'Done'
  const time = new Date(task.completed_at).toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  })
  return `Done at ${time}`
}
