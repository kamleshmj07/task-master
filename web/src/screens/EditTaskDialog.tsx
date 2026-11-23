import type { GoalRead, TaskRead } from '@task-master/api-client'
import { type FormEvent, useState } from 'react'

import { api, errorMessage } from '@/api'
import { Field } from '@/components/Field'
import { Modal } from '@/components/Modal'
import { TimeLimitField } from '@/components/TimeLimitField'
import { fromMinutes, plural, type TimeUnit, toMinutes } from '@/data'
import { formatDay } from '@/dates'

interface EditTaskDialogProps {
  task: TaskRead
  goals: GoalRead[]
  onSaved: () => void
  onDeleted: () => void
  onClose: () => void
}

/**
 * Edit a task's title, goal, time limit and due date, or delete it. A due
 * date can be brought forward here; moving it later is a postponement.
 */
export function EditTaskDialog({ task, goals, onSaved, onDeleted, onClose }: EditTaskDialogProps) {
  const initialLimit = fromMinutes(task.time_limit_minutes)
  const [title, setTitle] = useState(task.title)
  const [goalId, setGoalId] = useState(task.goal_id ?? '')
  const [limitAmount, setLimitAmount] = useState(initialLimit.amount)
  const [limitUnit, setLimitUnit] = useState<TimeUnit>(initialLimit.unit)
  const [dueDate, setDueDate] = useState(task.due_date ?? '')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const dated = task.due_date !== null
  const dueInfo = dated
    ? `You can bring the date forward here. To move it after ${formatDay(task.due_date ?? '')}, use Postpone, which asks why.`
    : 'Pick a date to schedule this Someday task.'

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const { error: apiError } = await api.PATCH('/tasks/{task_id}', {
      params: { path: { task_id: task.id } },
      body: {
        title,
        goal_id: goalId || null,
        time_limit_minutes: toMinutes(limitAmount, limitUnit),
        ...(dueDate !== (task.due_date ?? '') ? { due_date: dueDate || null } : {}),
      },
    })
    if (apiError) {
      setError(errorMessage(apiError))
      return
    }
    onSaved()
  }

  async function handleDelete() {
    const { error: apiError } = await api.DELETE('/tasks/{task_id}', {
      params: { path: { task_id: task.id } },
    })
    if (apiError) {
      setError(errorMessage(apiError))
      return
    }
    onDeleted()
  }

  if (confirmDelete) {
    return (
      <Modal title="Delete this task?" onClose={() => setConfirmDelete(false)}>
        <p>
          “{task.title}” will be deleted with its {plural(task.steps.length, 'step')}
          {task.postpone_count > 0 ? ' and its postponement history' : ''}. This cannot be undone.
        </p>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <div className="row">
          <button type="button" className="danger solid" onClick={() => void handleDelete()}>
            Delete task
          </button>
          <button type="button" onClick={() => setConfirmDelete(false)}>
            Keep it
          </button>
        </div>
      </Modal>
    )
  }

  return (
    <Modal title="Edit task" onClose={onClose}>
      <form className="stack" onSubmit={handleSubmit} aria-label="Edit task">
        <Field label="Task">
          {(id) => <input id={id} required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />}
        </Field>
        <div className="grid">
          <Field label="Goal">
            {(id) => (
              <select id={id} value={goalId} onChange={(e) => setGoalId(e.target.value)}>
                <option value="">No goal</option>
                {goals.map((goal) => (
                  <option key={goal.id} value={goal.id}>
                    {goal.title}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <TimeLimitField
            amount={limitAmount}
            unit={limitUnit}
            onAmountChange={setLimitAmount}
            onUnitChange={setLimitUnit}
          />
          <Field label="Due date" info={dueInfo}>
            {(id) => (
              <input
                id={id}
                type="date"
                required={dated}
                {...(task.due_date ? { max: task.due_date } : {})}
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
              />
            )}
          </Field>
        </div>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <div className="row between">
          <div className="row">
            <button type="submit" className="primary">
              Save changes
            </button>
            <button type="button" onClick={onClose}>
              Cancel
            </button>
          </div>
          <button type="button" className="ghost danger" onClick={() => setConfirmDelete(true)}>
            Delete task
          </button>
        </div>
      </form>
    </Modal>
  )
}
