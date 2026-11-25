import type { PostponementRead, PostponeReason, TaskRead } from '@task-master/api-client'
import { type FormEvent, useEffect, useState } from 'react'

import { api, errorMessage } from '@/api'
import { type GoalLabel, GoalTag } from '@/components/GoalTag'
import { InfoTip } from '@/components/InfoTip'
import { describeRepeat, postponementSummary, REASONS, timeLimitLabel } from '@/data'
import { daysBetween, dueLabel, formatDay } from '@/dates'
import { tipArticle } from '@/tips'
import { useNavigation } from '@/navigation'

interface TaskCardProps {
  task: TaskRead
  today: string
  goal: GoalLabel | null
  open: boolean
  onToggleOpen: () => void
  /** The task changed on the server; `allStepsDone` asks to confirm completion. */
  onChanged: (task: TaskRead, allStepsDone: boolean) => void
  onPostpone: () => void
  onEdit: () => void
}

/** One task row: status rail, title, its next step, facts; expands to its steps. */
export function TaskCard({
  task,
  today,
  goal,
  open,
  onToggleOpen,
  onChanged,
  onPostpone,
  onEdit,
}: TaskCardProps) {
  const done = task.status === 'done'
  const finished = task.steps.filter((step) => step.done).length
  const overdue = !done && task.due_date !== null && daysBetween(today, task.due_date) < 0
  const ready = !done && task.next_step === null
  const limit = timeLimitLabel(task.time_limit_minutes)
  const rail = overdue ? 'rail loss' : ready ? 'rail gain' : 'rail'
  const settled = done ? 'Completed' : 'Every step is done'

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
          </button>
          <div className="facts">
            <span className={overdue ? 'loss strong' : undefined}>{dueLabel(task.due_date, today)}</span>
            <span>
              {finished} of {task.steps.length} {task.steps.length === 1 ? 'step' : 'steps'}
            </span>
            {limit && <span>{limit} limit</span>}
            {task.repeat && <span>{describeRepeat(task.repeat)}</span>}
            {goal && <GoalTag goal={goal} />}
            {task.postpone_count > 0 && (
              <span className="loss strong">
                {postponementSummary(task.postpone_count, task.postponement_reasons)}
              </span>
            )}
          </div>
          <p className={done || ready ? 'next-block settled' : 'next-block'}>
            {done || ready ? (
              settled
            ) : (
              <>
                <span className="next-label">Next step</span>
                <span className="next-text">{task.next_step}</span>
              </>
            )}
          </p>
        </div>
        <div className="row nowrap">
          {!done && (
            <button type="button" onClick={onPostpone}>
              Postpone
            </button>
          )}
          <button type="button" className="ghost icon" aria-label={`Edit “${task.title}”`} onClick={onEdit}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 20h9" />
              <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
            </svg>
          </button>
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
      {open && task.postpone_count > 0 && <HistoryToggle task={task} />}
    </article>
  )
}

/** A task's steps as a numbered checklist; read-only once the task is done. */
export function StepList({ task, onChanged }: Pick<TaskCardProps, 'task' | 'onChanged'>) {
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState<number | null>(null)
  const [over, setOver] = useState<number | null>(null)
  // The step that just became next; it glows once to show what changed.
  const [glowId, setGlowId] = useState<string | null>(null)
  const nextIndex = task.steps.findIndex((step) => !step.done)
  const finished = task.status === 'done'
  const canReorder = !finished && task.steps.length > 1

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
      <div className="row">
        <h3 className="steps-title">Steps</h3>
        {canReorder && (
          <InfoTip label="Reordering steps">
            Drag a step by its handle to move it, or focus the handle and press the up and down
            arrow keys.
          </InfoTip>
        )}
      </div>
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
                disabled={finished}
                onChange={() => void handleToggle(step.id, !step.done)}
              />
            </label>
            {!finished && task.steps.length > 1 && (
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
      {finished && <p className="hint">This task is done, so its steps can no longer change. Reopen it to edit them.</p>}
      {!finished && (
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
      )}
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

const REASON_LABELS = Object.fromEntries(REASONS.map(({ value, label }) => [value, label])) as Record<
  PostponeReason,
  string
>

/** Every postponement of a task, newest first, with a guide for a repeated reason. */
function PostponementHistory({ task }: { task: TaskRead }) {
  const { go } = useNavigation()
  const [entries, setEntries] = useState<PostponementRead[] | null>(null)

  useEffect(() => {
    let current = true
    void (async () => {
      const { data } = await api.GET('/tasks/{task_id}/postponements', {
        params: { path: { task_id: task.id }, query: { limit: 100 } },
      })
      if (current) setEntries([...(data ?? [])].reverse())
    })()
    return () => {
      current = false
    }
  }, [task.id, task.postpone_count])

  const repeated = (Object.entries(task.postponement_reasons) as [PostponeReason, number][])
    .filter(([, count]) => count >= 2)
    .sort((a, b) => b[1] - a[1])[0]
  const guide = repeated ? tipArticle(repeated[0]) : undefined

  return (
    <div className="history">
      <h3 className="steps-title">History</h3>
      {guide && repeated && (
        <p className="small">
          {REASON_LABELS[repeated[0]]}, {repeated[1]} times.{' '}
          <button type="button" className="link" onClick={() => go('tips', { tip: repeated[0] })}>
            Read: {guide.title}
          </button>
        </p>
      )}
      <ol className="history-list">
        {entries?.map((entry) => (
          <li key={entry.id} className="history-entry">
            <span className="history-date">{formatDay(entry.created_at.slice(0, 10))}</span>
            <span>
              Moved to {entry.to_date ? formatDay(entry.to_date) : 'Someday'}
              <span className="muted">. {REASON_LABELS[entry.reason]}</span>
              {entry.note && <span className="muted">: “{entry.note}”</span>}
            </span>
          </li>
        ))}
      </ol>
    </div>
  )
}

/** "Show postponement history" button; the history loads only when opened. */
function HistoryToggle({ task }: { task: TaskRead }) {
  const [shown, setShown] = useState(false)
  return (
    <div className="history-toggle">
      <button type="button" className="link" aria-expanded={shown} onClick={() => setShown(!shown)}>
        {shown ? 'Hide postponement history' : 'Show postponement history'}
      </button>
      {shown && <PostponementHistory task={task} />}
    </div>
  )
}
