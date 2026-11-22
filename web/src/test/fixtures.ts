import type { RoutineRead, TaskRead } from '@task-master/api-client'

/** A to-do task with two unfinished steps, unless overridden. */
export function makeTask(overrides: Partial<TaskRead> = {}): TaskRead {
  const steps = overrides.steps ?? [
    { id: 's1', text: 'Find the policy', done: false },
    { id: 's2', text: 'Call the broker', done: false },
  ]
  return {
    id: 't1',
    goal_id: null,
    title: 'Renew insurance',
    time_limit_minutes: null,
    due_date: null,
    status: 'todo',
    postpone_count: 0,
    completed_at: null,
    created_at: '2026-11-22T00:00:00Z',
    updated_at: '2026-11-22T00:00:00Z',
    ...overrides,
    steps,
    next_step: steps.find((step) => !step.done)?.text ?? null,
  }
}

/** A daily routine running all of 2026, unless overridden. */
export function makeRoutine(overrides: Partial<RoutineRead> = {}): RoutineRead {
  return {
    id: 'r1',
    goal_id: null,
    title: 'Workout',
    frequency: 'daily',
    weekdays: null,
    day_of_month: null,
    start_date: '2026-01-01',
    end_date: '2026-12-31',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}
