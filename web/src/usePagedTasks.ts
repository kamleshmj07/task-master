import type { TaskCounts, TaskRead, TaskView } from '@task-master/api-client'
import { useCallback, useEffect, useState } from 'react'

import { api } from '@/api'

export const PAGE_SIZE = 50

export type { TaskView }
/** `'all'`, `'none'` (goal-less tasks) or a goal id. */
export type GoalFilter = string

function goalQuery(goal: GoalFilter) {
  if (goal === 'all') return {}
  if (goal === 'none') return { no_goal: true }
  return { goal_id: goal }
}

async function fetchPage(view: TaskView, goal: GoalFilter, offset: number): Promise<TaskRead[]> {
  const { data } = await api.GET('/tasks', {
    params: { query: { view, ...goalQuery(goal), limit: PAGE_SIZE, offset } },
  })
  return data ?? []
}

/** Fetch pages until `count` tasks are loaded or the list runs out. */
async function fetchFirst(view: TaskView, goal: GoalFilter, count: number): Promise<TaskRead[]> {
  const tasks: TaskRead[] = []
  while (tasks.length < count) {
    const page = await fetchPage(view, goal, tasks.length)
    tasks.push(...page)
    if (page.length < PAGE_SIZE) break
  }
  return tasks
}

/**
 * One view's tasks, loaded `PAGE_SIZE` at a time, plus server-side counts for
 * every view. `reload` keeps as many tasks loaded as before.
 */
export function usePagedTasks(view: TaskView, goal: GoalFilter) {
  const [tasks, setTasks] = useState<TaskRead[] | null>(null)
  const [counts, setCounts] = useState<TaskCounts | null>(null)

  const loadCounts = useCallback(async () => {
    const { data } = await api.GET('/tasks/counts', { params: { query: goalQuery(goal) } })
    setCounts(data ?? null)
  }, [goal])

  useEffect(() => {
    let current = true
    void (async () => {
      const [first] = await Promise.all([fetchFirst(view, goal, PAGE_SIZE), loadCounts()])
      if (current) setTasks(first)
    })()
    return () => {
      current = false
    }
  }, [view, goal, loadCounts])

  const loaded = tasks?.length ?? 0

  const reload = useCallback(async () => {
    const [refreshed] = await Promise.all([
      fetchFirst(view, goal, Math.max(loaded, PAGE_SIZE)),
      loadCounts(),
    ])
    setTasks(refreshed)
  }, [view, goal, loaded, loadCounts])

  const loadMore = useCallback(async () => {
    const page = await fetchPage(view, goal, loaded)
    setTasks((previous) => [...(previous ?? []), ...page])
  }, [view, goal, loaded])

  const total = counts?.[view] ?? loaded
  return { tasks, counts, remaining: Math.max(total - loaded, 0), reload, loadMore }
}
