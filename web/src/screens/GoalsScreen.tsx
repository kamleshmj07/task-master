import type { GoalRead, GoalStatus } from '@task-master/api-client'
import { type FormEvent, useState } from 'react'

import { api, errorMessage } from '@/api'
import { Field } from '@/components/Field'
import { Modal } from '@/components/Modal'
import { goalHealth, plural } from '@/data'
import { formatDay, todayIso } from '@/dates'
import { useResource } from '@/useResource'

async function loadAllGoals(): Promise<GoalRead[]> {
  const { data } = await api.GET('/goals', { params: { query: { limit: 100 } } })
  return data ?? []
}

const SECTIONS: { status: GoalStatus; label: string }[] = [
  { status: 'active', label: 'Active' },
  { status: 'completed', label: 'Completed' },
  { status: 'archived', label: 'Archived' },
]

/** Goals: outcomes worth working toward, each with its "why" and progress. */
export function GoalsScreen() {
  const goals = useResource(loadAllGoals)
  const [editing, setEditing] = useState<GoalRead | null>(null)
  const [deleting, setDeleting] = useState<GoalRead | null>(null)

  async function handleDelete(goal: GoalRead) {
    await api.DELETE('/goals/{goal_id}', { params: { path: { goal_id: goal.id } } })
    setDeleting(null)
    await goals.reload()
  }

  return (
    <section className="stack-lg" aria-labelledby="goals-heading">
      <div>
        <h1 id="goals-heading" className="page-title">
          Goals
        </h1>
        <p className="muted lede">The outcomes your tasks move you toward.</p>
      </div>

      <section className="card stack" aria-labelledby="new-goal-heading">
        <h2 id="new-goal-heading">New goal</h2>
        <GoalForm submitLabel="Add goal" onSaved={() => void goals.reload()} />
      </section>

      {SECTIONS.map(({ status, label }) => {
        const inSection = (goals.data ?? []).filter((goal) => goal.status === status)
        if (inSection.length === 0) return null
        return (
          <section key={status} className="stack-sm" aria-label={`${label} goals`}>
            <h2 className="group-head">
              {label} <span className="group-count">{inSection.length}</span>
            </h2>
            <ul className="plain-list stack-sm">
              {inSection.map((goal) => (
                <GoalCard
                  key={goal.id}
                  goal={goal}
                  onEdit={() => setEditing(goal)}
                  onDelete={() => setDeleting(goal)}
                />
              ))}
            </ul>
          </section>
        )
      })}

      {editing && (
        <Modal title="Edit goal" onClose={() => setEditing(null)}>
          <GoalForm
            goal={editing}
            submitLabel="Save changes"
            onSaved={() => {
              setEditing(null)
              void goals.reload()
            }}
            onCancel={() => setEditing(null)}
          />
        </Modal>
      )}

      {deleting && (
        <Modal title="Delete this goal?" onClose={() => setDeleting(null)}>
          <p>
            “{deleting.title}” will be deleted together with{' '}
            <strong>{plural(deleting.progress.total_tasks, 'task')}</strong> under it. This cannot be
            undone.
          </p>
          <div className="row">
            <button type="button" className="danger solid" onClick={() => void handleDelete(deleting)}>
              Delete goal and its tasks
            </button>
            <button type="button" onClick={() => setDeleting(null)}>
              Cancel
            </button>
          </div>
        </Modal>
      )}
    </section>
  )
}

function GoalCard({ goal, onEdit, onDelete }: { goal: GoalRead; onEdit: () => void; onDelete: () => void }) {
  const { progress } = goal
  const health = goalHealth(goal, todayIso())
  const percent = progress.total_tasks ? Math.round((progress.done_tasks / progress.total_tasks) * 100) : 0

  return (
    <li className="panel goal-card">
      <div className="row between nowrap">
        <div className="grow">
          <h3 className="goal-title">{goal.title}</h3>
          {goal.why && <p className="muted">{goal.why}</p>}
        </div>
        <div className="row nowrap">
          <button type="button" aria-label={`Edit “${goal.title}”`} onClick={onEdit}>
            Edit
          </button>
          <button type="button" className="ghost danger" aria-label={`Delete “${goal.title}”`} onClick={onDelete}>
            Delete
          </button>
        </div>
      </div>

      <div className="goal-progress">
        <div
          className="bar wide"
          role="progressbar"
          aria-label={`Progress of “${goal.title}”`}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
        >
          <span style={{ width: `${percent}%` }} />
        </div>
        <p className="small">
          {progress.total_tasks === 0
            ? 'No tasks yet'
            : `${progress.done_tasks} of ${plural(progress.total_tasks, 'task')} done`}
        </p>
      </div>

      <ul className="facts goal-facts">
        {health.deadline && <li className={health.deadlineUrgent ? 'loss strong' : undefined}>{health.deadline}</li>}
        {progress.next_due_task && (
          <li>
            Next due: {progress.next_due_task.title}, {formatDay(progress.next_due_task.due_date)}
          </li>
        )}
        {health.quiet && <li className="loss strong">{health.quiet}</li>}
      </ul>
    </li>
  )
}

interface GoalFormProps {
  /** The goal to edit; leave out to create a new one. */
  goal?: GoalRead
  submitLabel: string
  onSaved: () => void
  onCancel?: () => void
}

function GoalForm({ goal, submitLabel, onSaved, onCancel }: GoalFormProps) {
  const [title, setTitle] = useState(goal?.title ?? '')
  const [why, setWhy] = useState(goal?.why ?? '')
  const [deadline, setDeadline] = useState(goal?.deadline ?? '')
  const [status, setStatus] = useState<GoalStatus>(goal?.status ?? 'active')
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const fields = { title, why: why || null, deadline: deadline || null }
    const { error: apiError } = goal
      ? await api.PATCH('/goals/{goal_id}', { params: { path: { goal_id: goal.id } }, body: { ...fields, status } })
      : await api.POST('/goals', { body: fields })
    if (apiError) {
      setError(errorMessage(apiError))
      return
    }
    if (!goal) {
      setTitle('')
      setWhy('')
      setDeadline('')
    }
    setError(null)
    onSaved()
  }

  return (
    <form className="stack" onSubmit={handleSubmit} aria-label={goal ? 'Edit goal' : 'New goal'}>
      <div className="grid">
        <Field label="Goal">
          {(id) => <input id={id} required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />}
        </Field>
        <Field
          label="Why it matters"
          info="The reason behind the goal. Seeing it again is what keeps you going when a task feels like a chore."
        >
          {(id) => <input id={id} maxLength={2000} value={why} onChange={(e) => setWhy(e.target.value)} />}
        </Field>
        <Field label="Deadline" info="Optional. You get a notification when it is a week away.">
          {(id) => <input id={id} type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} />}
        </Field>
        {goal && (
          <Field
            label="Status"
            info="Completed and archived goals keep their history. Their finished tasks are cleared 90 days later."
          >
            {(id) => (
              <select id={id} value={status} onChange={(e) => setStatus(e.target.value as GoalStatus)}>
                <option value="active">Active</option>
                <option value="completed">Completed</option>
                <option value="archived">Archived</option>
              </select>
            )}
          </Field>
        )}
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <div className="row">
        <button type="submit" className="primary">
          {submitLabel}
        </button>
        {onCancel && (
          <button type="button" onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
    </form>
  )
}
