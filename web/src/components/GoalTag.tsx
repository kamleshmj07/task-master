import type { GoalRead } from '@task-master/api-client'

/** What a task needs to show which goal it serves. */
export type GoalLabel = Pick<GoalRead, 'title' | 'color'>

/** A goal's name with its colour dot, for task facts and chips. */
export function GoalTag({ goal }: { goal: GoalLabel }) {
  return (
    <span className="goal-tag" data-goal-color={goal.color}>
      <span className="goal-dot" aria-hidden="true" />
      {goal.title}
    </span>
  )
}
