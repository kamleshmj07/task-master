import type { GoalRead, TaskRead } from '@task-master/api-client'
import { type FormEvent, useState } from 'react'

import { api, errorMessage } from '@/api'
import { Field } from '@/components/Field'
import { GoalPicker } from '@/components/GoalPicker'
import { Modal } from '@/components/Modal'
import { RepeatField } from '@/components/RepeatField'
import { TimeLimitField } from '@/components/TimeLimitField'
import {
  fromMinutes,
  plural,
  repeatDraft,
  type RepeatDraft,
  repeatFromDraft,
  type TimeUnit,
  toMinutes,
} from '@/data'
import { formatDay } from '@/dates'

interface EditTaskDialogProps {
  task: TaskRead
  goals: GoalRead[]
  onSaved: () => void
  onDeleted: () => void
  onClose: () => void
  onGoalCreated?: () => void
}

/**
 * Edit a task's title, goal, time limit, due date and repeat, or delete it.
 * A due date can be brought forward here; moving it later is a postponement.
 */
export function EditTaskDialog({ task, goals, onSaved, onDeleted, onClose, onGoalCreated }: EditTaskDialogProps) {
  const initialLimit = fromMinutes(task.time_limit_minutes)
  const [title, setTitle] = useState(task.title)
  const [goalId, setGoalId] = useState(task.goal_id ?? '')
  const [limitAmount, setLimitAmount] = useState(initialLimit.amount)
  const [limitUnit, setLimitUnit] = useState<TimeUnit>(initialLimit.unit)
  const [dueDate, setDueDate] = useState(task.due_date ?? '')
  const [repeat, setRepeat] = useState<RepeatDraft>(repeatDraft(task.repeat))
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const dated = task.due_date !== null
  const dueInfo = dated
    ? `You can bring the date forward here. To move it after ${formatDay(task.due_date ?? '')}, use Postpone, which asks why.`
    : 'Pick a date to schedule this Someday task.'

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const rule = repeatFromDraft(repeat)
    const ruleChanged = JSON.stringify(rule) !== JSON.stringify(repeatFromDraft(repeatDraft(task.repeat)))
    const { error: apiError } = await api.PATCH('/tasks/{task_id}', {
      params: { path: { task_id: task.id } },
      body: {
        title,
        goal_id: goalId || null,
        time_limit_minutes: toMinutes(limitAmount, limitUnit),
        ...(dueDate !== (task.due_date ?? '') ? { due_date: dueDate || null } : {}),
        ...(ruleChanged ? { repeat: rule } : {}),
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
          <GoalPicker
            goals={goals}
            value={goalId}
            onChange={setGoalId}
            {...(onGoalCreated ? { onGoalCreated } : {})}
            info="The outcome this task moves you toward. Optional: everyday chores can stay goal-less or go under Essentials."
          />
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
                required={dated || repeat.frequency !== 'none'}
                {...(task.due_date ? { max: task.due_date } : {})}
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
              />
            )}
          </Field>
        </div>
        <RepeatField draft={repeat} dueDate={dueDate} onChange={setRepeat} />
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
