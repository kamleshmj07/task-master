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

/** One task row: status rail, title, its next step, facts; expands to its steps. */
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
  const ready = !done && task.next_step === null
  const limit = timeLimitLabel(task.time_limit_minutes)
  const rail = overdue ? 'rail loss' : ready ? 'rail gain' : 'rail'
  const next = done ? 'Completed' : ready ? 'Every step is done' : `Next: ${task.next_step}`

  async function handleToggleTask() {
    const { data } = await api.PATCH('/tasks/{task_id}', {
      params: { path: { task_id: task.id } },
      body: { status: done ? 'todo' : 'done' },
    })
    if (data) onChanged(data, false)
  }

  return (
    <article className={open ? 'task-row open' : 'task-row'}>
      <span className={rail} aria-hidden="true" />
      <div className="task-head">
        <input
          type="checkbox"
          className="check"
          aria-label={`Mark “${task.title}” ${done ? 'not done' : 'done'}`}
          checked={done}
          onChange={() => void handleToggleTask()}
        />
        <div className="grow">
          <button type="button" className="unstyled task-title" aria-expanded={open} onClick={onToggleOpen}>
            <span className={done ? 'title done' : 'title'}>{task.title}</span>
            <span className={done || ready ? 'next-step settled' : 'next-step'}>{next}</span>
          </button>
          <div className="facts">
            <span className={overdue ? 'loss strong' : undefined}>{dueLabel(task.due_date, today)}</span>
            <span>
              {finished} of {task.steps.length} {task.steps.length === 1 ? 'step' : 'steps'}
            </span>
            {limit && <span>{limit} limit</span>}
            {goalTitle && <span>{goalTitle}</span>}
            {task.postpone_count > 0 && (
              <span className="loss strong">
                Postponed {task.postpone_count} {task.postpone_count === 1 ? 'time' : 'times'}
              </span>
            )}
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
  const [dragging, setDragging] = useState<number | null>(null)
  const [over, setOver] = useState<number | null>(null)
  // The step that just became next; it glows once to show what changed.
  const [glowId, setGlowId] = useState<string | null>(null)
  const nextIndex = task.steps.findIndex((step) => !step.done)
  const canReorder = task.steps.length > 1

  async function handleToggle(stepId: string, done: boolean) {
    const { data } = await api.PATCH('/tasks/{task_id}/steps/{step_id}', {
      params: { path: { task_id: task.id, step_id: stepId } },
      body: { done },
    })
    if (!data) return
    const allDone = data.steps.every((step) => step.done)
    setGlowId(data.steps.find((step) => !step.done)?.id ?? null)
    onChanged(data, done && allDone && data.status === 'todo')
  }

  async function handleMove(from: number, to: number) {
    if (from === to || to < 0 || to >= task.steps.length) return
    const ids = task.steps.map((step) => step.id)
    const [moved] = ids.splice(from, 1)
    if (moved === undefined) return
    ids.splice(to, 0, moved)
    const { data, error: apiError } = await api.PUT('/tasks/{task_id}/steps/order', {
      params: { path: { task_id: task.id } },
      body: { step_ids: ids },
    })
    if (apiError || !data) {
      setError(errorMessage(apiError))
      return
    }
    setError(null)
    onChanged(data, false)
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
      {canReorder && <p className="hint">Drag a step by its handle to reorder it.</p>}
      <ol className="trail" aria-label={`Steps for “${task.title}”`}>
        {task.steps.map((step, index) => (
          <li
            key={step.id}
            className={stepClass(step.id === glowId, over === index && dragging !== index)}
            draggable={canReorder}
            onDragStart={(event) => {
              event.dataTransfer.effectAllowed = 'move'
              setDragging(index)
            }}
            onDragOver={(event) => {
              if (dragging === null) return
              event.preventDefault()
              setOver(index)
            }}
            onDragLeave={() => setOver(null)}
            onDrop={(event) => {
              event.preventDefault()
              if (dragging !== null) void handleMove(dragging, index)
              setDragging(null)
              setOver(null)
            }}
            onDragEnd={() => {
              setDragging(null)
              setOver(null)
            }}
          >
            {canReorder && (
              <button
                type="button"
                className="ghost icon handle"
                aria-label={`Reorder step “${step.text}”, use arrow keys`}
                onKeyDown={(event) => {
                  if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
                    event.preventDefault()
                    void handleMove(index, index + (event.key === 'ArrowUp' ? -1 : 1))
                  }
                }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <circle cx="9" cy="6" r="1.5" />
                  <circle cx="15" cy="6" r="1.5" />
                  <circle cx="9" cy="12" r="1.5" />
                  <circle cx="15" cy="12" r="1.5" />
                  <circle cx="9" cy="18" r="1.5" />
                  <circle cx="15" cy="18" r="1.5" />
                </svg>
              </button>
            )}
            <span
              className={step.done ? 'node done' : index === nextIndex && task.status === 'todo' ? 'node next' : 'node'}
              aria-hidden="true"
            >
              {index + 1}
            </span>
            <label className="choice grow">
              <span className={step.done ? 'step-text done' : index === nextIndex ? 'step-text next' : 'step-text'}>
                {step.text}
              </span>
              <input
                type="checkbox"
                className="tick"
                checked={step.done}
                onChange={() => void handleToggle(step.id, !step.done)}
              />
            </label>
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
      </ol>
      <form className="row add-step" onSubmit={handleAdd}>
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

function stepClass(glow: boolean, dropTarget: boolean): string {
  return ['step', glow && 'glow', dropTarget && 'drop-target'].filter(Boolean).join(' ')
}
