import type { DueRoutine, PlanRead, TaskRead } from '@task-master/api-client'
import { useCallback, useState } from 'react'

import { api, errorMessage } from '@/api'
import { addDays, formatDay, todayIso } from '@/dates'
import { useResource } from '@/useResource'

async function loadPlan(day: string): Promise<PlanRead | null> {
  const { data } = await api.GET('/plans/{plan_date}', {
    params: { path: { plan_date: day } },
  })
  return data ?? null
}

async function loadOpenTasks(): Promise<TaskRead[]> {
  const { data } = await api.GET('/tasks', {
    params: { query: { status: 'todo', limit: 100 } },
  })
  return data ?? []
}

/** One day: the Top 3 one-off tasks, and separately, the day's routines. */
export function TodayScreen() {
  const today = todayIso()
  const [day, setDay] = useState(today)
  const plan = useResource(useCallback(() => loadPlan(day), [day]))
  const openTasks = useResource(loadOpenTasks)
  const [error, setError] = useState<string | null>(null)

  const topThree = plan.data?.top_three ?? []
  const isPast = day < today

  async function savePlan(taskIds: string[]) {
    const { error: apiError } = await api.PUT('/plans/{plan_date}', {
      params: { path: { plan_date: day } },
      body: { task_ids: taskIds },
    })
    setError(apiError ? errorMessage(apiError) : null)
    await plan.reload()
  }

  const ids = topThree.map((item) => item.task.id)
  const move = (index: number, offset: number) => {
    const next = [...ids]
    const [moved] = next.splice(index, 1)
    if (moved) next.splice(index + offset, 0, moved)
    void savePlan(next)
  }

  async function handleToggleTask(task: TaskRead) {
    await api.PATCH('/tasks/{task_id}', {
      params: { path: { task_id: task.id } },
      body: { status: task.status === 'done' ? 'todo' : 'done' },
    })
    await Promise.all([plan.reload(), openTasks.reload()])
  }

  const candidates = (openTasks.data ?? []).filter((task) => !ids.includes(task.id))

  return (
    <section className="stack" aria-labelledby="today-heading">
      <div className="row between">
        <button type="button" aria-label="Previous day" onClick={() => setDay(addDays(day, -1))}>
          ‹
        </button>
        <h2 id="today-heading">{day === today ? `Today · ${formatDay(day)}` : formatDay(day)}</h2>
        <button type="button" aria-label="Next day" onClick={() => setDay(addDays(day, 1))}>
          ›
        </button>
      </div>

      {plan.data && <CapacityMeter capacity={plan.data.capacity} />}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}

      <div className="card stack">
        <h3>Top 3</h3>
        {topThree.length === 0 && <p className="muted">Pick up to three tasks that matter most.</p>}
        <ol className="list">
          {topThree.map(({ rank, task }, index) => (
            <li key={task.id} className="item row">
              <span className="rank">{rank}</span>
              <input
                type="checkbox"
                aria-label={`Mark "${task.title}" ${task.status === 'done' ? 'not done' : 'done'}`}
                checked={task.status === 'done'}
                onChange={() => void handleToggleTask(task)}
              />
              <div className="grow">
                <p className={task.status === 'done' ? 'title done' : 'title'}>{task.title}</p>
                <p className="muted">Next: {task.next_action}</p>
              </div>
              {!isPast && (
                <>
                  <button
                    type="button"
                    aria-label={`Move "${task.title}" up`}
                    disabled={index === 0}
                    onClick={() => move(index, -1)}
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    aria-label={`Move "${task.title}" down`}
                    disabled={index === topThree.length - 1}
                    onClick={() => move(index, 1)}
                  >
                    ↓
                  </button>
                  <button
                    type="button"
                    aria-label={`Remove "${task.title}" from Top 3`}
                    onClick={() => void savePlan(ids.filter((id) => id !== task.id))}
                  >
                    Remove
                  </button>
                </>
              )}
            </li>
          ))}
        </ol>
        {!isPast && topThree.length < 3 && candidates.length > 0 && (
          <label>
            Add a task
            <select
              value=""
              onChange={(event) => void savePlan([...ids, event.target.value])}
            >
              <option value="" disabled>
                Choose…
              </option>
              {candidates.map((task) => (
                <option key={task.id} value={task.id}>
                  {task.title}
                  {task.due_date ? ` (due ${formatDay(task.due_date)})` : ' (Someday)'}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      <RoutineChecklist
        day={day}
        routines={plan.data?.routines ?? []}
        canTick={day <= today}
        onChanged={() => void plan.reload()}
      />
    </section>
  )
}

function CapacityMeter({ capacity }: { capacity: PlanRead['capacity'] }) {
  const { planned_minutes: planned, limit_minutes: limit, over } = capacity
  return (
    <div className={over ? 'capacity over' : 'capacity'}>
      <meter min={0} max={limit} value={Math.min(planned, limit)} aria-label="Planned time" />
      <p>
        {planned} of {limit} min planned
        {over && <strong className="loss"> · over capacity, consider dropping something</strong>}
      </p>
    </div>
  )
}

interface RoutineChecklistProps {
  day: string
  routines: DueRoutine[]
  canTick: boolean
  onChanged: () => void
}

function RoutineChecklist({ day, routines, canTick, onChanged }: RoutineChecklistProps) {
  async function handleToggle({ routine, done }: DueRoutine) {
    const params = { path: { routine_id: routine.id, day } }
    if (done) await api.DELETE('/routines/{routine_id}/completions/{day}', { params })
    else await api.PUT('/routines/{routine_id}/completions/{day}', { params })
    onChanged()
  }

  return (
    <div className="card stack">
      <h3>Routines</h3>
      {routines.length === 0 && <p className="muted">No routines due.</p>}
      <ul className="list">
        {routines.map((due) => (
          <li key={due.routine.id} className="item row">
            <input
              type="checkbox"
              aria-label={`Tick "${due.routine.title}"`}
              checked={due.done}
              disabled={!canTick}
              onChange={() => void handleToggle(due)}
            />
            <span className={due.done ? 'grow title done' : 'grow title'}>
              {due.routine.title}
            </span>
            {due.streak > 0 && <span className="gain">{due.streak}-day streak</span>}
          </li>
        ))}
      </ul>
    </div>
  )
}
