import type { GoalRead, RoutineRead, TaskRead } from '@task-master/api-client'

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
    postponement_reasons: {},
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
    title: 'Workout',
    time_limit_minutes: null,
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

/** An active goal with no tasks yet, unless overridden. */
export function makeGoal(overrides: Partial<GoalRead> = {}): GoalRead {
  return {
    id: 'g1',
    title: 'Essentials',
    why: null,
    deadline: null,
    status: 'active',
    created_at: '2026-11-01T00:00:00Z',
    updated_at: '2026-11-20T00:00:00Z',
    progress: {
      total_tasks: 0,
      done_tasks: 0,
      next_due_task: null,
      last_moved_at: '2026-11-20T00:00:00Z',
    },
    ...overrides,
  }
}
