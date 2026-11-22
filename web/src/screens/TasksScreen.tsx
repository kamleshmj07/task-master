import type { PostponeResponse, TaskRead } from '@task-master/api-client'
import { useCallback, useState } from 'react'

import { api } from '@/api'
import { Modal } from '@/components/Modal'
import { groupScheduled, loadGoals } from '@/data'
import { todayIso } from '@/dates'
import { NewTaskPanel } from '@/screens/NewTaskPanel'
import { PostponeDialog, SuggestionCard } from '@/screens/PostponeForm'
import { TaskCard } from '@/screens/TaskCard'
import { useResource } from '@/useResource'

type View = 'scheduled' | 'someday' | 'done'
type GoalFilter = 'all' | 'none' | string

const VIEWS: { id: View; label: string }[] = [
  { id: 'scheduled', label: 'Scheduled' },
  { id: 'someday', label: 'Someday' },
  { id: 'done', label: 'Done' },
]

const EMPTY_HINTS: Record<View, string> = {
  scheduled: 'Add a task with a due date to see it here.',
  someday: 'Tasks without a date land here.',
  done: 'Finished tasks show up here.',
}

async function loadAllTasks(): Promise<TaskRead[]> {
  const [open, done] = await Promise.all([
    api.GET('/tasks', { params: { query: { status: 'todo', limit: 100 } } }),
    api.GET('/tasks', { params: { query: { status: 'done', limit: 100 } } }),
  ])
  return [...(open.data ?? []), ...(done.data ?? [])]
}

function viewOf(task: TaskRead): View {
  if (task.status === 'done') return 'done'
  return task.due_date === null ? 'someday' : 'scheduled'
}

/** Tasks in three views: Scheduled (grouped by when), Someday and Done. */
export function TasksScreen() {
  const today = todayIso()
  const tasks = useResource(loadAllTasks)
  const goals = useResource(loadGoals)
  const [view, setView] = useState<View>('scheduled')
  const [goalFilter, setGoalFilter] = useState<GoalFilter>('all')
  const [adding, setAdding] = useState(false)
  const [openId, setOpenId] = useState<string | null>(null)
  const [postponing, setPostponing] = useState<TaskRead | null>(null)
  const [confirming, setConfirming] = useState<TaskRead | null>(null)
  const [suggestion, setSuggestion] = useState<PostponeResponse | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const goalTitle = useCallback(
    (id: string | null) => goals.data?.find((goal) => goal.id === id)?.title ?? null,
    [goals.data],
  )

  const matchesGoal = (task: TaskRead) =>
    goalFilter === 'all' || (goalFilter === 'none' ? task.goal_id === null : task.goal_id === goalFilter)
  const filtered = (tasks.data ?? []).filter(matchesGoal)
  const inView = filtered.filter((task) => viewOf(task) === view)
  const count = (id: View) => filtered.filter((task) => viewOf(task) === id).length
  const groups =
    view === 'scheduled'
      ? groupScheduled(inView, today)
      : [{ id: view, label: view === 'someday' ? 'No date yet' : 'Completed', tasks: inView }].filter(
          (group) => group.tasks.length > 0,
        )

  function handleChanged(_task: TaskRead, allStepsDone: boolean) {
    if (allStepsDone) setConfirming(_task)
    void tasks.reload()
  }

  async function handleConfirmComplete(task: TaskRead) {
    await api.PATCH('/tasks/{task_id}', {
      params: { path: { task_id: task.id } },
      body: { status: 'done' },
    })
    setConfirming(null)
    setNotice(`“${task.title}” completed.`)
    await tasks.reload()
  }

  return (
    <section className="stack-lg" aria-labelledby="tasks-heading">
      <div className="row between wrap-end">
        <div>
          <h1 id="tasks-heading">Tasks</h1>
          <p className="muted">Every task starts with a concrete first step.</p>
        </div>
        {!adding && (
          <button type="button" className="primary large" onClick={() => setAdding(true)}>
            + New task
          </button>
        )}
      </div>

      {notice && (
        <div className="notice row between" role="status">
          <span>{notice}</span>
          <button type="button" className="ghost" onClick={() => setNotice(null)}>
            Dismiss
          </button>
        </div>
      )}
      {suggestion && <SuggestionCard result={suggestion} onDismiss={() => setSuggestion(null)} />}

      {adding && (
        <NewTaskPanel
          goals={goals.data ?? []}
          onGoalCreated={() => void goals.reload()}
          onClose={() => setAdding(false)}
          onCreated={(title, someday) => {
            setAdding(false)
            setView(someday ? 'someday' : 'scheduled')
            setNotice(`“${title}” added to ${someday ? 'Someday' : 'Scheduled'}.`)
            void tasks.reload()
          }}
        />
      )}

      <div className="stack-sm">
        <div className="segmented" role="tablist" aria-label="Task views">
          {VIEWS.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={view === id}
              onClick={() => setView(id)}
            >
              {label} <span className="count">{count(id)}</span>
            </button>
          ))}
        </div>
        <div className="chips" role="group" aria-label="Filter by goal">
          {[
            { id: 'all', title: 'All goals' },
            ...(goals.data ?? []),
            { id: 'none', title: 'No goal' },
          ].map(({ id, title }) => (
            <button
              key={id}
              type="button"
              className="chip"
              aria-pressed={goalFilter === id}
              onClick={() => setGoalFilter(id)}
            >
              {title}
            </button>
          ))}
        </div>
      </div>

      {tasks.data && groups.length === 0 && (
        <div className="card empty">
          <p className="title">Nothing here</p>
          <p className="muted">{EMPTY_HINTS[view]}</p>
        </div>
      )}

      {groups.map((group) => (
        <section key={group.id} className="stack-sm" aria-label={group.label}>
          <h2 className={`group-head ${group.id}`}>
            {group.label} <span className="muted">{group.tasks.length}</span>
          </h2>
          {group.tasks.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              today={today}
              goalTitle={goalTitle(task.goal_id)}
              open={openId === task.id}
              onToggleOpen={() => setOpenId(openId === task.id ? null : task.id)}
              onChanged={handleChanged}
              onPostpone={() => {
                setSuggestion(null)
                setPostponing(task)
              }}
            />
          ))}
        </section>
      ))}

      {postponing && (
        <PostponeDialog
          task={postponing}
          onClose={() => setPostponing(null)}
          onPostponed={(result) => {
            setPostponing(null)
            setSuggestion(result)
            void tasks.reload()
          }}
        />
      )}

      {confirming && (
        <Modal title="All steps done" onClose={() => setConfirming(null)}>
          <p>Mark “{confirming.title}” as complete?</p>
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
    </section>
  )
}
