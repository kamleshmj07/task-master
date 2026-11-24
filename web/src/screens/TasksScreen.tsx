import type { PostponeResponse, TaskRead } from '@task-master/api-client'
import { useCallback, useState } from 'react'

import { api } from '@/api'
import { Modal } from '@/components/Modal'
import { groupReview, groupScheduled, loadGoals, type TaskGroup } from '@/data'
import { todayIso } from '@/dates'
import { EditTaskDialog } from '@/screens/EditTaskDialog'
import { EmptyState } from '@/components/EmptyState'
import { NewTaskPanel } from '@/screens/NewTaskPanel'
import { PostponeDialog, TipDialog } from '@/screens/PostponeForm'
import { TaskCard } from '@/screens/TaskCard'
import { type GoalFilter, type TaskView as View, usePagedTasks } from '@/usePagedTasks'
import { useResource } from '@/useResource'

const VIEWS: { id: View; label: string }[] = [
  { id: 'scheduled', label: 'Scheduled' },
  { id: 'review', label: 'Review' },
  { id: 'someday', label: 'Someday' },
  { id: 'done', label: 'Done' },
]

const SUBTITLES: Record<View, string> = {
  scheduled: 'Each task shows its next step. Start there.',
  review: 'Overdue tasks, and tasks whose steps are all done, wait here for a decision.',
  someday: 'Ideas with no date yet. Give one a date when you are ready.',
  done: 'Finished tasks stay here for 90 days.',
}

const EMPTY_HINTS: Record<View, string> = {
  scheduled: 'Add a task with a due date to see it here.',
  review: 'Overdue tasks and tasks with every step done show up here.',
  someday: 'Tasks without a date land here.',
  done: 'Finished tasks from the last 90 days show up here.',
}

/** Tasks in three views: Scheduled (grouped by when), Someday and Done. */
export function TasksScreen() {
  const today = todayIso()
  const goals = useResource(loadGoals)
  const [view, setView] = useState<View>('scheduled')
  const [goalFilter, setGoalFilter] = useState<GoalFilter>('all')
  const tasks = usePagedTasks(view, goalFilter)
  const [adding, setAdding] = useState(false)
  const [openId, setOpenId] = useState<string | null>(null)
  const [postponing, setPostponing] = useState<TaskRead | null>(null)
  const [confirming, setConfirming] = useState<TaskRead | null>(null)
  const [editingTask, setEditingTask] = useState<TaskRead | null>(null)
  const [suggestion, setSuggestion] = useState<PostponeResponse | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const goalTitle = useCallback(
    (id: string | null) => goals.data?.find((goal) => goal.id === id)?.title ?? null,
    [goals.data],
  )

  const inView = tasks.tasks ?? []
  const count = (id: View) => tasks.counts?.[id] ?? 0
  const noTasksAtAll =
    goalFilter === 'all' && tasks.counts !== null && VIEWS.every(({ id }) => count(id) === 0)
  const groups = groupsFor(view, inView, today)

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
          <h1 id="tasks-heading" className="page-title">
            Tasks
          </h1>
          <p className="muted lede">{SUBTITLES[view]}</p>
        </div>
        {!adding && (
          <button type="button" className="primary large" onClick={() => setAdding(true)}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" aria-hidden="true">
              <path d="M12 5v14M5 12h14" />
            </svg>
            New task
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
      {suggestion && (
        <TipDialog
          result={suggestion}
          onDismiss={() => setSuggestion(null)}
          onOpenSteps={() => {
            setView(suggestion.task.due_date ? 'scheduled' : 'someday')
            setOpenId(suggestion.task.id)
            setSuggestion(null)
          }}
        />
      )}

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
        <div className="tabs" role="tablist" aria-label="Task views">
          {VIEWS.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={view === id}
              onClick={() => setView(id)}
            >
              {label}{' '}
              <span className={id === 'review' && count(id) > 0 ? 'count loss' : 'count'}>
                {count(id)}
              </span>
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

      {noTasksAtAll && !adding && (
        <EmptyState icon="tasks" title="Nothing on your list yet" actionLabel="New task" onAction={() => setAdding(true)}>
          Pick something you've been putting off. Break it into steps, starting with one so small it's easy.
        </EmptyState>
      )}
      {tasks.tasks && groups.length === 0 && !noTasksAtAll && (
        <div className="panel empty">
          <p className="title">Nothing here</p>
          <p className="muted">{EMPTY_HINTS[view]}</p>
        </div>
      )}

      {groups.map((group) => (
        <section key={group.id} className="stack-sm" aria-label={group.label}>
          <h2 className="group-head">
            {group.label} <span className="group-count">{group.tasks.length}</span>
          </h2>
          <div className="panel">
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
              onEdit={() => setEditingTask(task)}
            />
          ))}
          </div>
        </section>
      ))}

      {tasks.remaining > 0 && (
        <button type="button" className="load-more" onClick={() => void tasks.loadMore()}>
          Load {tasks.remaining} more
        </button>
      )}

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

      {editingTask && (
        <EditTaskDialog
          task={editingTask}
          goals={goals.data ?? []}
          onGoalCreated={() => void goals.reload()}
          onClose={() => setEditingTask(null)}
          onSaved={() => {
            setNotice(`Saved changes to “${editingTask.title}”.`)
            setEditingTask(null)
            void tasks.reload()
          }}
          onDeleted={() => {
            setNotice(`Deleted “${editingTask.title}”.`)
            setEditingTask(null)
            void tasks.reload()
          }}
        />
      )}

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
    </section>
  )
}

function groupsFor(view: View, tasks: TaskRead[], today: string): TaskGroup[] {
  if (view === 'scheduled') return groupScheduled(tasks, today)
  if (view === 'review') return groupReview(tasks)
  const label = view === 'someday' ? 'No date yet' : 'Completed in the last 90 days'
  return tasks.length > 0 ? [{ id: view, label, tasks }] : []
}
