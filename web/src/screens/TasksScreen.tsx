import type { GoalRead, PostponeResponse, TaskRead } from '@task-master/api-client'
import { type FormEvent, useCallback, useState } from 'react'

import { api, errorMessage } from '@/api'
import { loadGoals } from '@/data'
import { formatDay } from '@/dates'
import { PostponeForm, SuggestionCard } from '@/screens/PostponeForm'
import { useResource } from '@/useResource'

type View = 'scheduled' | 'someday' | 'done'

const VIEWS: { value: View; label: string }[] = [
  { value: 'scheduled', label: 'Scheduled' },
  { value: 'someday', label: 'Someday' },
  { value: 'done', label: 'Done' },
]

async function loadTasks(view: View): Promise<TaskRead[]> {
  const query =
    view === 'done'
      ? { status: 'done' as const }
      : { status: 'todo' as const, someday: view === 'someday' }
  const { data } = await api.GET('/tasks', { params: { query: { ...query, limit: 100 } } })
  return data ?? []
}

/** All tasks, split into Scheduled, Someday and Done. */
export function TasksScreen() {
  const [view, setView] = useState<View>('scheduled')
  const tasks = useResource(useCallback(() => loadTasks(view), [view]))
  const goals = useResource(loadGoals)
  const [suggestion, setSuggestion] = useState<PostponeResponse | null>(null)

  const goalTitle = (id: string | null) =>
    goals.data?.find((goal) => goal.id === id)?.title ?? null

  return (
    <section className="stack" aria-labelledby="tasks-heading">
      <h2 id="tasks-heading">Tasks</h2>
      <NewTaskForm goals={goals.data ?? []} onCreated={() => void tasks.reload()} />
      {suggestion && (
        <SuggestionCard result={suggestion} onDismiss={() => setSuggestion(null)} />
      )}
      <div role="tablist" aria-label="Task views" className="tabs">
        {VIEWS.map(({ value, label }) => (
          <button
            key={value}
            role="tab"
            aria-selected={view === value}
            onClick={() => setView(value)}
          >
            {label}
          </button>
        ))}
      </div>
      {tasks.data?.length === 0 && <p className="muted">Nothing here.</p>}
      <ul className="list">
        {tasks.data?.map((task) => (
          <TaskRow
            key={task.id}
            task={task}
            goalTitle={goalTitle(task.goal_id)}
            onChanged={() => void tasks.reload()}
            onPostponed={(result) => {
              setSuggestion(result)
              void tasks.reload()
            }}
          />
        ))}
      </ul>
    </section>
  )
}

interface TaskRowProps {
  task: TaskRead
  goalTitle: string | null
  onChanged: () => void
  onPostponed: (result: PostponeResponse) => void
}

function TaskRow({ task, goalTitle, onChanged, onPostponed }: TaskRowProps) {
  const [postponing, setPostponing] = useState(false)
  const done = task.status === 'done'

  async function handleToggleDone() {
    await api.PATCH('/tasks/{task_id}', {
      params: { path: { task_id: task.id } },
      body: { status: done ? 'todo' : 'done' },
    })
    onChanged()
  }

  async function handleDelete() {
    await api.DELETE('/tasks/{task_id}', { params: { path: { task_id: task.id } } })
    onChanged()
  }

  return (
    <li className="card item">
      <div className="row">
        <input
          type="checkbox"
          aria-label={`Mark "${task.title}" ${done ? 'not done' : 'done'}`}
          checked={done}
          onChange={() => void handleToggleDone()}
        />
        <div className="grow">
          <p className={done ? 'title done' : 'title'}>{task.title}</p>
          <p className="muted">Next: {task.next_action}</p>
          <p className="meta">
            {task.due_date ? formatDay(task.due_date) : 'Someday'}
            {task.estimate_minutes ? ` · ${task.estimate_minutes} min` : ''}
            {goalTitle ? ` · ${goalTitle}` : ''}
            {task.postpone_count > 0 && (
              <span className="loss"> · postponed {task.postpone_count}×</span>
            )}
          </p>
        </div>
        {!done && (
          <button type="button" onClick={() => setPostponing(!postponing)}>
            Postpone
          </button>
        )}
        <button
          type="button"
          className="danger"
          aria-label={`Delete "${task.title}"`}
          onClick={() => void handleDelete()}
        >
          Delete
        </button>
      </div>
      {postponing && (
        <PostponeForm
          task={task}
          onCancel={() => setPostponing(false)}
          onPostponed={(result) => {
            setPostponing(false)
            onPostponed(result)
          }}
        />
      )}
    </li>
  )
}

function NewTaskForm({ goals, onCreated }: { goals: GoalRead[]; onCreated: () => void }) {
  const [title, setTitle] = useState('')
  const [nextAction, setNextAction] = useState('')
  const [goalId, setGoalId] = useState('')
  const [estimate, setEstimate] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const { error: apiError } = await api.POST('/tasks', {
      body: {
        title,
        next_action: nextAction,
        goal_id: goalId || null,
        estimate_minutes: estimate ? Number(estimate) : null,
        due_date: dueDate || null,
      },
    })
    if (apiError) {
      setError(errorMessage(apiError))
      return
    }
    setTitle('')
    setNextAction('')
    setEstimate('')
    setDueDate('')
    setError(null)
    onCreated()
  }

  return (
    <form className="card grid" onSubmit={handleSubmit} aria-label="New task">
      <label>
        Task
        <input required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label>
        Next action
        <input
          required
          maxLength={500}
          placeholder="The very first physical step"
          value={nextAction}
          onChange={(e) => setNextAction(e.target.value)}
        />
      </label>
      <label>
        Goal
        <select value={goalId} onChange={(e) => setGoalId(e.target.value)}>
          <option value="">No goal</option>
          {goals.map((goal) => (
            <option key={goal.id} value={goal.id}>
              {goal.title}
            </option>
          ))}
        </select>
      </label>
      <label>
        Estimate (min)
        <input
          type="number"
          min={1}
          max={1440}
          value={estimate}
          onChange={(e) => setEstimate(e.target.value)}
        />
      </label>
      <label>
        Due date
        <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
      </label>
      <p className="hint">Leave the date empty to put it in Someday.</p>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <button type="submit" className="primary">
        Add task
      </button>
    </form>
  )
}
