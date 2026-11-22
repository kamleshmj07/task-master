import type { TaskRead } from '@task-master/api-client'
import { type FormEvent, useState } from 'react'

import { api, errorMessage } from '@/api'
import { timeLimitLabel } from '@/data'
import { daysBetween, dueLabel } from '@/dates'

interface TaskCardProps {
  task: TaskRead
  today: string
  goalTitle: string | null
  open: boolean
  onToggleOpen: () => void
  /** The task changed on the server; `allStepsDone` asks to confirm completion. */
  onChanged: (task: TaskRead, allStepsDone: boolean) => void
  onPostpone: () => void
}

/** One task: title, next step and facts; expands to its step checklist. */
export function TaskCard({
  task,
  today,
  goalTitle,
  open,
  onToggleOpen,
  onChanged,
  onPostpone,
}: TaskCardProps) {
  const done = task.status === 'done'
  const finished = task.steps.filter((step) => step.done).length
  const overdue = !done && task.due_date !== null && daysBetween(today, task.due_date) < 0
  const dueToday = !done && task.due_date === today
  const limit = timeLimitLabel(task.time_limit_minutes)

  async function handleToggleTask() {
    const { data } = await api.PATCH('/tasks/{task_id}', {
      params: { path: { task_id: task.id } },
      body: { status: done ? 'todo' : 'done' },
    })
    if (data) onChanged(data, false)
  }

  return (
    <article className={open ? 'task open' : 'task'}>
      <div className="task-head">
        <input
          type="checkbox"
          className="check"
          aria-label={`Mark “${task.title}” ${done ? 'not done' : 'done'}`}
          checked={done}
          onChange={() => void handleToggleTask()}
        />
        <div className="grow stack-xs">
          <button type="button" className="unstyled task-title" aria-expanded={open} onClick={onToggleOpen}>
            <span className={done ? 'title done' : 'title'}>{task.title}</span>
            <span className="next">
              <strong>Next:</strong> {done ? 'All done' : (task.next_step ?? 'All steps done. Mark complete?')}
            </span>
          </button>
          <div className="pills">
            <span className={overdue ? 'pill loss' : dueToday ? 'pill today' : 'pill'}>
              {dueLabel(task.due_date, today)}
            </span>
            <span className="pill">
              <span className="bar" aria-hidden="true">
                <span style={{ width: `${(finished / task.steps.length) * 100}%` }} />
              </span>
              {finished}/{task.steps.length} steps
            </span>
            {limit && <span className="pill">{limit} limit</span>}
            {goalTitle && <span className="pill">{goalTitle}</span>}
            {task.postpone_count > 0 && <span className="pill loss">Postponed {task.postpone_count}×</span>}
          </div>
        </div>
        <div className="row nowrap">
          {!done && (
            <button type="button" onClick={onPostpone}>
              Postpone
            </button>
          )}
          <button
            type="button"
            className="ghost icon"
            aria-label={`${open ? 'Hide' : 'Show'} steps for “${task.title}”`}
            aria-expanded={open}
            onClick={onToggleOpen}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" className={open ? 'flip' : undefined}>
              <path d="m6 9 6 6 6-6" />
            </svg>
          </button>
        </div>
      </div>
      {open && <StepList task={task} onChanged={onChanged} />}
    </article>
  )
}

function StepList({ task, onChanged }: Pick<TaskCardProps, 'task' | 'onChanged'>) {
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)
  const nextIndex = task.steps.findIndex((step) => !step.done)

  async function handleToggle(stepId: string, done: boolean) {
    const { data } = await api.PATCH('/tasks/{task_id}/steps/{step_id}', {
      params: { path: { task_id: task.id, step_id: stepId } },
      body: { done },
    })
    if (!data) return
    const allDone = data.steps.every((step) => step.done)
    onChanged(data, done && allDone && data.status === 'todo')
  }

  async function handleDelete(stepId: string) {
    const { data, error: apiError } = await api.DELETE('/tasks/{task_id}/steps/{step_id}', {
      params: { path: { task_id: task.id, step_id: stepId } },
    })
    if (apiError || !data) {
      setError(errorMessage(apiError))
      return
    }
    setError(null)
    onChanged(data, false)
  }

  async function handleAdd(event: FormEvent) {
    event.preventDefault()
    const { data, error: apiError } = await api.POST('/tasks/{task_id}/steps', {
      params: { path: { task_id: task.id } },
      body: { text: draft },
    })
    if (apiError || !data) {
      setError(errorMessage(apiError))
      return
    }
    setDraft('')
    setError(null)
    onChanged(data, false)
  }

  return (
    <div className="steps">
      <p className="eyebrow">Steps</p>
      <ul className="list">
        {task.steps.map((step, index) => (
          <li key={step.id} className="step">
            <label className="choice grow">
              <input
                type="checkbox"
                className="check"
                checked={step.done}
                onChange={() => void handleToggle(step.id, !step.done)}
              />
              <span className={step.done ? 'done' : index === nextIndex ? 'step-next' : undefined}>
                {step.text}
              </span>
            </label>
            {index === nextIndex && task.status === 'todo' && <span className="pill today">Next</span>}
            {task.steps.length > 1 && (
              <button
                type="button"
                className="ghost icon"
                aria-label={`Remove step “${step.text}”`}
                onClick={() => void handleDelete(step.id)}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              </button>
            )}
          </li>
        ))}
      </ul>
      <form className="row" onSubmit={handleAdd}>
        <input
          className="grow"
          aria-label={`Add a step to “${task.title}”`}
          placeholder="Add a step"
          required
          maxLength={500}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <button type="submit">Add</button>
      </form>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </div>
  )
}
