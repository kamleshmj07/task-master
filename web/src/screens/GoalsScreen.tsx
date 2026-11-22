import type { GoalRead, GoalStatus } from '@task-master/api-client'
import { type FormEvent, useState } from 'react'

import { api, errorMessage } from '@/api'
import { formatDay } from '@/dates'
import { useResource } from '@/useResource'

async function loadAllGoals(): Promise<GoalRead[]> {
  const { data } = await api.GET('/goals', { params: { query: { limit: 100 } } })
  return data ?? []
}

const STATUSES: GoalStatus[] = ['active', 'completed', 'archived']

/** Goals: outcomes worth working toward, each with its "why". */
export function GoalsScreen() {
  const goals = useResource(loadAllGoals)

  async function handleStatus(goal: GoalRead, status: GoalStatus) {
    await api.PATCH('/goals/{goal_id}', {
      params: { path: { goal_id: goal.id } },
      body: { status },
    })
    await goals.reload()
  }

  async function handleDelete(goal: GoalRead) {
    const confirmed = window.confirm(`Delete "${goal.title}" and all of its tasks?`)
    if (!confirmed) return
    await api.DELETE('/goals/{goal_id}', { params: { path: { goal_id: goal.id } } })
    await goals.reload()
  }

  return (
    <section className="stack" aria-labelledby="goals-heading">
      <h2 id="goals-heading">Goals</h2>
      <NewGoalForm onCreated={() => void goals.reload()} />
      <ul className="list">
        {goals.data?.map((goal) => (
          <li key={goal.id} className="card item row">
            <div className="grow">
              <p className="title">{goal.title}</p>
              {goal.why && <p className="muted">Why: {goal.why}</p>}
              {goal.deadline && <p className="meta">By {formatDay(goal.deadline)}</p>}
            </div>
            <label>
              <span className="visually-hidden">Status of "{goal.title}"</span>
              <select
                value={goal.status}
                onChange={(e) => void handleStatus(goal, e.target.value as GoalStatus)}
              >
                {STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="danger"
              aria-label={`Delete "${goal.title}"`}
              onClick={() => void handleDelete(goal)}
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}

function NewGoalForm({ onCreated }: { onCreated: () => void }) {
  const [title, setTitle] = useState('')
  const [why, setWhy] = useState('')
  const [deadline, setDeadline] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const { error: apiError } = await api.POST('/goals', {
      body: { title, why: why || null, deadline: deadline || null },
    })
    if (apiError) {
      setError(errorMessage(apiError))
      return
    }
    setTitle('')
    setWhy('')
    setDeadline('')
    setError(null)
    onCreated()
  }

  return (
    <form className="card grid" onSubmit={handleSubmit} aria-label="New goal">
      <label>
        Goal
        <input required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label>
        Why it matters
        <input maxLength={2000} value={why} onChange={(e) => setWhy(e.target.value)} />
      </label>
      <label>
        Deadline
        <input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
      </label>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <button type="submit" className="primary">
        Add goal
      </button>
    </form>
  )
}
