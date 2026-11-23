import type { DueRoutine, PlanRead, TaskRead } from '@task-master/api-client'
import { useCallback, useState } from 'react'

import { api, errorMessage } from '@/api'
import { Modal } from '@/components/Modal'
import { addDays, formatDay, todayIso } from '@/dates'
import { StepList } from '@/screens/TaskCard'
import { PAGE_SIZE } from '@/usePagedTasks'
import { useResource } from '@/useResource'

async function loadPlan(day: string): Promise<PlanRead | null> {
  const { data } = await api.GET('/plans/{plan_date}', {
    params: { path: { plan_date: day } },
  })
  return data ?? null
}

/** Open tasks, soonest due first, `count` at most: the Top 3 candidates. */
async function loadOpenTasks(count: number): Promise<TaskRead[]> {
  const tasks: TaskRead[] = []
  while (tasks.length < count) {
    const { data } = await api.GET('/tasks', {
      params: { query: { status: 'todo', limit: PAGE_SIZE, offset: tasks.length } },
    })
    tasks.push(...(data ?? []))
    if ((data ?? []).length < PAGE_SIZE) break
  }
  return tasks
}

/** One day: the Top 3 one-off tasks, and separately, the day's routines. */
export function TodayScreen() {
  const today = todayIso()
  const [day, setDay] = useState(today)
  const plan = useResource(useCallback(() => loadPlan(day), [day]))
  const [candidateLimit, setCandidateLimit] = useState(PAGE_SIZE)
  const openTasks = useResource(
    useCallback(() => loadOpenTasks(candidateLimit), [candidateLimit]),
  )
  const [error, setError] = useState<string | null>(null)
  const [openId, setOpenId] = useState<string | null>(null)
  const [confirming, setConfirming] = useState<TaskRead | null>(null)

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

  async function handleConfirmComplete(task: TaskRead) {
    await api.PATCH('/tasks/{task_id}', {
      params: { path: { task_id: task.id } },
      body: { status: 'done' },
    })
    setConfirming(null)
    await Promise.all([plan.reload(), openTasks.reload()])
  }

  const candidates = (openTasks.data ?? []).filter((task) => !ids.includes(task.id))

  return (
    <section className="stack" aria-labelledby="today-heading">
      <div className="row between">
        <button type="button" aria-label="Previous day" onClick={() => setDay(addDays(day, -1))}>
          ‹
        </button>
        <h1 id="today-heading">{day === today ? `Today · ${formatDay(day)}` : formatDay(day)}</h1>
        <button type="button" aria-label="Next day" onClick={() => setDay(addDays(day, 1))}>
          ›
        </button>
      </div>

      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}

      <div className="card stack">
        <h2>Top 3</h2>
        {topThree.length === 0 && <p className="muted">Pick up to three tasks that matter most.</p>}
        <ol className="list">
          {topThree.map(({ rank, task }, index) => {
            const open = openId === task.id
            const finished = task.steps.filter((step) => step.done).length
            return (
            <li key={task.id} className="top-three-item">
              <div className="item row">
              <span className="rank">{rank}</span>
              <input
                type="checkbox"
                aria-label={`Mark "${task.title}" ${task.status === 'done' ? 'not done' : 'done'}`}
                checked={task.status === 'done'}
                onChange={() => void handleToggleTask(task)}
              />
              <div className="grow">
                <p className={task.status === 'done' ? 'title done' : 'title'}>{task.title}</p>
                <p className="muted">
                  Next: {task.next_step ?? 'All steps done'}
                </p>
              </div>
              <button
                type="button"
                aria-expanded={open}
                aria-label={`${open ? 'Hide' : 'Show'} steps for “${task.title}”, ${finished} of ${task.steps.length} done`}
                onClick={() => setOpenId(open ? null : task.id)}
              >
                Steps {finished}/{task.steps.length}
              </button>
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
              </div>
              {open && (
                <StepList
                  task={task}
                  onChanged={(changed, allStepsDone) => {
                    if (allStepsDone) setConfirming(changed)
                    void plan.reload()
                  }}
                />
              )}
            </li>
            )
          })}
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
        {!isPast && topThree.length < 3 && (openTasks.data?.length ?? 0) >= candidateLimit && (
          <div>
            <button
              type="button"
              className="ghost accent"
              onClick={() => setCandidateLimit(candidateLimit + PAGE_SIZE)}
            >
              Show more tasks to choose from
            </button>
          </div>
        )}
      </div>

      {confirming && (
        <Modal title="Every step is done" onClose={() => setConfirming(null)}>
          <p>Mark “{confirming.title}” complete?</p>
          <div className="row">
            <button type="button" className="primary" onClick={() => void handleConfirmComplete(confirming)}>
              Mark complete
            </button>
            <button type="button" onClick={() => setConfirming(null)}>
              Not yet
            </button>
          </div>
        </Modal>
      )}

      <RoutineChecklist
        day={day}
        routines={plan.data?.routines ?? []}
        canTick={day <= today}
        onChanged={() => void plan.reload()}
      />
    </section>
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
      <h2>Routines</h2>
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
