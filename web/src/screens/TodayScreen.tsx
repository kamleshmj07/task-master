import type {
  DueRoutine,
  GoalRead,
  HeadsUpItem,
  PlanRead,
  PlanSuggestion,
  PostponeResponse,
  TaskRead,
} from '@task-master/api-client'
import { useCallback, useState } from 'react'

import { api, errorMessage } from '@/api'
import { useAuth } from '@/authContext'
import { Modal } from '@/components/Modal'
import { describeRepeat, loadGoals, plural, timeLimitLabel } from '@/data'
import { addDays, dueLabel, formatDay, todayIso } from '@/dates'
import { useNavigation } from '@/navigation'
import { EditTaskDialog } from '@/screens/EditTaskDialog'
import { NewTaskPanel } from '@/screens/NewTaskPanel'
import { PostponeDialog, TipDialog } from '@/screens/PostponeForm'
import { StepList } from '@/screens/TaskCard'
import {
  doneAt,
  greeting,
  headsUpReason,
  longDay,
  SLOT_LABELS,
  stepsDone,
  suggestionReason,
} from '@/today'
import { PAGE_SIZE } from '@/usePagedTasks'
import { useResource } from '@/useResource'

async function loadPlan(day: string): Promise<PlanRead | null> {
  const { data } = await api.GET('/plans/{plan_date}', {
    params: { path: { plan_date: day } },
  })
  return data ?? null
}

/** Open tasks, soonest due first, `count` at most: everything that can be picked. */
async function loadOpenTasks(count: number): Promise<TaskRead[]> {
  const tasks: TaskRead[] = []
  while (tasks.length < count) {
    const { data } = await api.GET('/tasks', {
      params: { query: { status: 'todo', limit: PAGE_SIZE, offset: tasks.length } },
    })
    tasks.push(...(data ?? []))
    if ((data ?? []).length < PAGE_SIZE) break
  }
  return tasks
}

/**
 * The landing page: a greeting, the day's three tasks with the first one lit
 * and its steps open, the day's routines, and what needs a decision.
 */
export function TodayScreen() {
  const today = todayIso()
  const { user } = useAuth()
  const [day, setDay] = useState(today)
  // Read once: the greeting need not change while the page is open.
  const [openedAt] = useState(() => new Date())
  const plan = useResource(useCallback(() => loadPlan(day), [day]))
  const goals = useResource(loadGoals)
  const [error, setError] = useState<string | null>(null)
  const [postponing, setPostponing] = useState<TaskRead | null>(null)
  const [tip, setTip] = useState<PostponeResponse | null>(null)
  const [editing, setEditing] = useState<TaskRead | null>(null)
  const [confirming, setConfirming] = useState<TaskRead | null>(null)

  const isPast = day < today
  const isToday = day === today
  const topThree = plan.data?.top_three ?? []
  const ids = topThree.map((item) => item.task.id)
  const goalTitles = new Map((goals.data ?? []).map((goal: GoalRead) => [goal.id, goal.title]))

  async function savePlan(taskIds: string[]) {
    const { error: apiError } = await api.PUT('/plans/{plan_date}', {
      params: { path: { plan_date: day } },
      body: { task_ids: taskIds },
    })
    setError(apiError ? errorMessage(apiError) : null)
    await plan.reload()
  }

  async function setStatus(task: TaskRead, status: 'todo' | 'done') {
    const { error: apiError } = await api.PATCH('/tasks/{task_id}', {
      params: { path: { task_id: task.id } },
      body: { status },
    })
    setError(apiError ? errorMessage(apiError) : null)
    setConfirming(null)
    await plan.reload()
  }

  const routines = plan.data?.routines ?? []
  const doneTasks = topThree.filter((item) => item.task.status === 'done').length
  const doneRoutines = routines.filter((due) => due.done).length

  return (
    <section className="today stack-lg" aria-labelledby="today-heading">
      <header className="today-head">
        <div className="stack-sm">
          <h1 id="today-heading">{isToday ? greeting(openedAt, user?.display_name) : longDay(day)}</h1>
          <div className="row today-day">
            <button type="button" className="icon-button" aria-label="Previous day" onClick={() => setDay(addDays(day, -1))}>
              <Chevron direction="left" />
            </button>
            <span>{isToday ? longDay(day) : isPast ? 'A past day' : 'A day ahead'}</span>
            <button type="button" className="icon-button" aria-label="Next day" onClick={() => setDay(addDays(day, 1))}>
              <Chevron direction="right" />
            </button>
            {!isToday && (
              <button type="button" className="ghost" onClick={() => setDay(today)}>
                Back to today
              </button>
            )}
          </div>
        </div>
        <div className="glance" aria-label="The day so far">
          <Glance label="Your three" done={doneTasks} total={topThree.length} />
          <Glance label="Routines" done={doneRoutines} total={routines.length} />
        </div>
      </header>

      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}

      <div className="today-columns">
        <div className="today-main">
          <TopThree
            plan={plan.data}
            day={day}
            today={today}
            readOnly={isPast}
            goalTitles={goalTitles}
            onSave={(next) => void savePlan(next)}
            onChanged={(task, allStepsDone) => {
              if (allStepsDone) setConfirming(task)
              void plan.reload()
            }}
            onComplete={(task) => void setStatus(task, 'done')}
            onReopen={(task) => void setStatus(task, 'todo')}
            onPostpone={setPostponing}
            onEdit={setEditing}
          />
          {!isPast && topThree.length < 3 && (
            <Suggestions
              suggestions={plan.data?.suggestions ?? []}
              today={today}
              planned={ids}
              goals={goals.data ?? []}
              onGoalCreated={() => void goals.reload()}
              onAdd={(taskId) => void savePlan([...ids, taskId])}
              onCreated={() => void plan.reload()}
            />
          )}
        </div>
        <div className="today-side">
          <Routines day={day} routines={routines} canTick={!(day > today)} onChanged={() => void plan.reload()} />
          {isToday && (
            <HeadsUp
              items={plan.data?.heads_up ?? []}
              today={today}
              onPostpone={setPostponing}
              onComplete={(task) => void setStatus(task, 'done')}
            />
          )}
        </div>
      </div>

      {confirming && (
        <Modal title="Every step is done" onClose={() => setConfirming(null)}>
          <p>Mark “{confirming.title}” complete?</p>
          <div className="row">
            <button type="button" className="primary" onClick={() => void setStatus(confirming, 'done')}>
              Mark complete
            </button>
            <button type="button" onClick={() => setConfirming(null)}>
              Not yet
            </button>
          </div>
        </Modal>
      )}
      {postponing && (
        <PostponeDialog
          task={postponing}
          onClose={() => setPostponing(null)}
          onPostponed={(result) => {
            setPostponing(null)
            setTip(result)
            void plan.reload()
          }}
        />
      )}
      {tip && <TipDialog result={tip} onDismiss={() => setTip(null)} />}
      {editing && (
        <EditTaskDialog
          task={editing}
          goals={goals.data ?? []}
          onGoalCreated={() => void goals.reload()}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            void plan.reload()
          }}
          onDeleted={() => {
            setEditing(null)
            void plan.reload()
          }}
        />
      )}
    </section>
  )
}

function Glance({ label, done, total }: { label: string; done: number; total: number }) {
  return (
    <div className="glance-card">
      <span className="glance-label">{label}</span>
      <span className="glance-value">{total === 0 ? 'None yet' : `${done} of ${total} done`}</span>
      {total > 0 && (
        <span className="glance-bar" aria-hidden="true">
          {Array.from({ length: total }, (_, index) => (
            <span key={index} className={index < done ? 'done' : undefined} />
          ))}
        </span>
      )}
    </div>
  )
}

interface TopThreeProps {
  plan: PlanRead | null
  day: string
  today: string
  readOnly: boolean
  goalTitles: Map<string, string>
  onSave: (taskIds: string[]) => void
  onChanged: (task: TaskRead, allStepsDone: boolean) => void
  onComplete: (task: TaskRead) => void
  onReopen: (task: TaskRead) => void
  onPostpone: (task: TaskRead) => void
  onEdit: (task: TaskRead) => void
}

/** The day's three, in order; the first open one is lit with its steps open. */
function TopThree({ plan, day, today, readOnly, goalTitles, onSave, onChanged, onComplete, onReopen, onPostpone, onEdit }: TopThreeProps) {
  const [changing, setChanging] = useState(false)
  // Steps the user opened or closed; the focus task starts open.
  const [toggled, setToggled] = useState<Record<string, boolean>>({})
  const items = plan?.top_three ?? []
  const ids = items.map((item) => item.task.id)
  const focusId = items.find((item) => item.task.status === 'todo')?.task.id

  function move(index: number, offset: number) {
    const next = [...ids]
    const [moved] = next.splice(index, 1)
    if (moved) next.splice(index + offset, 0, moved)
    onSave(next)
  }

  const heading = day === today ? 'Your three for today' : `Your three for ${formatDay(day)}`

  return (
    <section className="panel today-three" aria-labelledby="three-heading">
      <div className="today-panel-head">
        <h2 id="three-heading">{heading}</h2>
        {!readOnly && items.length > 0 && (
          <button type="button" aria-pressed={changing} onClick={() => setChanging(!changing)}>
            {changing ? 'Done changing' : 'Change'}
          </button>
        )}
      </div>
      {items.length === 0 && readOnly && <p className="today-empty muted">Nothing was picked for this day.</p>}
      <ol className="today-list">
        {items.map(({ rank, task }, index) => {
          const isFocus = task.id === focusId
          const open = toggled[task.id] ?? isFocus
          return (
            <li key={task.id} className={isFocus ? 'today-item focus' : 'today-item'}>
              <ThreeItem
                rank={rank}
                task={task}
                today={today}
                goalTitle={task.goal_id ? goalTitles.get(task.goal_id) : undefined}
                focus={isFocus}
                open={open}
                readOnly={readOnly}
                onToggle={() => setToggled({ ...toggled, [task.id]: !open })}
                onChanged={onChanged}
                onComplete={onComplete}
                onReopen={onReopen}
                onPostpone={onPostpone}
                onEdit={onEdit}
              />
              {changing && (
                <div className="row today-change">
                  <button type="button" aria-label={`Move “${task.title}” up`} disabled={index === 0} onClick={() => move(index, -1)}>
                    Move up
                  </button>
                  <button
                    type="button"
                    aria-label={`Move “${task.title}” down`}
                    disabled={index === items.length - 1}
                    onClick={() => move(index, 1)}
                  >
                    Move down
                  </button>
                  <button type="button" className="ghost danger" aria-label={`Remove “${task.title}” from your three`} onClick={() => onSave(ids.filter((id) => id !== task.id))}>
                    Remove
                  </button>
                </div>
              )}
            </li>
          )
        })}
        {!readOnly &&
          SLOT_LABELS.slice(items.length).map((label, index) => (
            <li key={label} className="today-item slot">
              <span className={items.length + index === 0 ? 'today-rank lit' : 'today-rank'} aria-hidden="true">
                {items.length + index + 1}
              </span>
              <span className="muted">{label}: pick a task below</span>
            </li>
          ))}
      </ol>
    </section>
  )
}

interface ThreeItemProps {
  rank: number
  task: TaskRead
  today: string
  goalTitle: string | undefined
  focus: boolean
  open: boolean
  readOnly: boolean
  onToggle: () => void
  onChanged: (task: TaskRead, allStepsDone: boolean) => void
  onComplete: (task: TaskRead) => void
  onReopen: (task: TaskRead) => void
  onPostpone: (task: TaskRead) => void
  onEdit: (task: TaskRead) => void
}

function ThreeItem({ rank, task, today, goalTitle, focus, open, readOnly, onToggle, onChanged, onComplete, onReopen, onPostpone, onEdit }: ThreeItemProps) {
  const done = task.status === 'done'
  const finished = stepsDone(task)
  const limit = timeLimitLabel(task.time_limit_minutes)

  if (done) {
    return (
      <div className="today-row">
        <span className="today-rank done" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 6 9 17l-5-5" />
          </svg>
        </span>
        <div className="grow">
          <h3 className="today-title done">
            <span className="visually-hidden">{rank}. </span>
            {task.title}
          </h3>
          <p className="gain small">{doneAt(task)}</p>
        </div>
        {!readOnly && (
          <button type="button" className="ghost" aria-label={`Undo “${task.title}”`} onClick={() => onReopen(task)}>
            Undo
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="stack-sm">
      <div className="today-row">
        <span className={focus ? 'today-rank lit' : 'today-rank'} aria-hidden="true">
          {rank}
        </span>
        <div className="grow">
          {focus && <p className="today-start">Start here</p>}
          <h3 className={focus ? 'today-title focus' : 'today-title'}>
            <span className="visually-hidden">{rank}. </span>
            {task.title}
          </h3>
          <div className="facts">
            <span className={task.due_date && task.due_date < today ? 'loss strong' : undefined}>{dueLabel(task.due_date, today)}</span>
            <span>
              {finished} of {plural(task.steps.length, 'step')}
            </span>
            {limit && <span>{limit} limit</span>}
            {task.repeat && <span>{describeRepeat(task.repeat)}</span>}
            {goalTitle && <span>{goalTitle}</span>}
          </div>
          {!focus && task.next_step && <p className="today-next-quiet">Next: {task.next_step}</p>}
        </div>
        {!focus && (
          <button
            type="button"
            aria-expanded={open}
            aria-label={`${open ? 'Hide' : 'Show'} steps for “${task.title}”, ${finished} of ${task.steps.length} done`}
            onClick={onToggle}
          >
            Steps {finished}/{task.steps.length}
          </button>
        )}
      </div>
      {focus && task.next_step && (
        <div className="next-block today-next">
          <span className="next-label">Next step</span>
          <span className="next-text">{task.next_step}</span>
        </div>
      )}
      {open && <StepList task={task} onChanged={onChanged} />}
      {focus && !readOnly && (
        <div className="row today-actions">
          {task.next_step === null && (
            <button type="button" className="primary" onClick={() => onComplete(task)}>
              Mark complete
            </button>
          )}
          <button type="button" onClick={() => onPostpone(task)}>
            Postpone
          </button>
          <button type="button" className="ghost" onClick={() => onEdit(task)}>
            Edit
          </button>
          <button
            type="button"
            className="ghost"
            aria-expanded={open}
            aria-label={`${open ? 'Hide' : 'Show'} steps for “${task.title}”, ${finished} of ${task.steps.length} done`}
            onClick={onToggle}
          >
            {open ? 'Hide steps' : 'Show steps'}
          </button>
        </div>
      )}
    </div>
  )
}

interface SuggestionsProps {
  suggestions: PlanSuggestion[]
  today: string
  planned: string[]
  goals: GoalRead[]
  onGoalCreated: () => void
  onAdd: (taskId: string) => void
  onCreated: () => void
}

/** What to pick for the free slots: yesterday's leftovers first, then the rest. */
function Suggestions({ suggestions, today, planned, goals, onGoalCreated, onAdd, onCreated }: SuggestionsProps) {
  const [choosing, setChoosing] = useState(false)
  const [adding, setAdding] = useState(false)
  const leftOver = suggestions.filter((s) => s.kind === 'left_over')
  const others = suggestions.filter((s) => s.kind !== 'left_over')
  const empty = planned.length === 0

  return (
    <section className="card stack today-suggest" aria-labelledby="suggest-heading">
      <div className="stack-sm">
        <h2 id="suggest-heading">{empty ? 'What would make today a good day?' : `Room for ${plural(3 - planned.length, 'more task')}`}</h2>
        {empty && <p className="muted">Pick up to three tasks. The first one is where you start.</p>}
      </div>
      {leftOver.length > 0 && <SuggestionGroup title="Left from yesterday" items={leftOver} today={today} onAdd={onAdd} />}
      {others.length > 0 && <SuggestionGroup title="Suggested from your tasks" items={others} today={today} onAdd={onAdd} />}
      {suggestions.length === 0 && <p className="muted">No suggestions right now. Choose any open task, or add a new one.</p>}
      {choosing && <ChooseTask planned={planned} onAdd={onAdd} onClose={() => setChoosing(false)} />}
      {adding && (
        <NewTaskPanel
          goals={goals}
          onGoalCreated={onGoalCreated}
          onClose={() => setAdding(false)}
          onCreated={() => {
            setAdding(false)
            onCreated()
          }}
        />
      )}
      {!choosing && !adding && (
        <div className="row">
          <button type="button" onClick={() => setChoosing(true)}>
            Choose another task
          </button>
          <button type="button" className="ghost" onClick={() => setAdding(true)}>
            New task
          </button>
        </div>
      )}
    </section>
  )
}

function SuggestionGroup({ title, items, today, onAdd }: { title: string; items: PlanSuggestion[]; today: string; onAdd: (taskId: string) => void }) {
  return (
    <div className="stack-sm">
      <h3 className="field-label">{title}</h3>
      <ul className="today-suggestions">
        {items.map((suggestion) => (
          <li key={suggestion.task.id} className="today-suggestion">
            <div className="grow">
              <p className="today-suggestion-title">{suggestion.task.title}</p>
              <p className={suggestion.kind === 'overdue' ? 'small loss' : 'small muted'}>{suggestionReason(suggestion, today)}</p>
            </div>
            <button
              type="button"
              className="primary"
              aria-label={`Add “${suggestion.task.title}” to your three`}
              onClick={() => onAdd(suggestion.task.id)}
            >
              Add
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Any open task not yet picked, soonest due first. */
function ChooseTask({ planned, onAdd, onClose }: { planned: string[]; onAdd: (taskId: string) => void; onClose: () => void }) {
  const [limit, setLimit] = useState(PAGE_SIZE)
  const tasks = useResource(useCallback(() => loadOpenTasks(limit), [limit]))
  const candidates = (tasks.data ?? []).filter((task) => !planned.includes(task.id))

  return (
    <div className="stack-sm">
      <label>
        Choose a task
        <select value="" onChange={(event) => event.target.value && onAdd(event.target.value)}>
          <option value="" disabled>
            {tasks.data === null ? 'Loading…' : 'Choose…'}
          </option>
          {candidates.map((task) => (
            <option key={task.id} value={task.id}>
              {task.title}
              {task.due_date ? ` (due ${formatDay(task.due_date)})` : ' (Someday)'}
            </option>
          ))}
        </select>
      </label>
      <div className="row">
        {(tasks.data?.length ?? 0) >= limit && (
          <button type="button" className="ghost" onClick={() => setLimit(limit + PAGE_SIZE)}>
            Show more tasks
          </button>
        )}
        <button type="button" className="ghost" onClick={onClose}>
          Cancel
        </button>
      </div>
    </div>
  )
}

interface RoutinesProps {
  day: string
  routines: DueRoutine[]
  canTick: boolean
  onChanged: () => void
}

function Routines({ day, routines, canTick, onChanged }: RoutinesProps) {
  const { go } = useNavigation()

  async function handleToggle({ routine, done }: DueRoutine) {
    const params = { path: { routine_id: routine.id, day } }
    if (done) await api.DELETE('/routines/{routine_id}/completions/{day}', { params })
    else await api.PUT('/routines/{routine_id}/completions/{day}', { params })
    onChanged()
  }

  const done = routines.filter((due) => due.done).length
  return (
    <section className="panel" aria-labelledby="routines-heading">
      <div className="today-panel-head">
        <h2 id="routines-heading">Routines</h2>
        {routines.length > 0 && (
          <span className="muted small">
            {done} of {routines.length}
          </span>
        )}
      </div>
      {routines.length === 0 ? (
        <div className="today-empty stack-sm">
          <p className="muted">No routines due this day.</p>
          <div>
            <button type="button" className="link" onClick={() => go('routines')}>
              Set up routines
            </button>
          </div>
        </div>
      ) : (
        <ul className="today-routines">
          {routines.map((due) => (
            <li key={due.routine.id}>
              <label className={due.done ? 'today-routine done' : 'today-routine'}>
                <input type="checkbox" checked={due.done} disabled={!canTick} onChange={() => void handleToggle(due)} />
                <span className="today-routine-text">
                  <span className="today-routine-title">{due.routine.title}</span>
                  {due.routine.time_limit_minutes !== null && (
                    <span className="today-routine-meta">{timeLimitLabel(due.routine.time_limit_minutes)}</span>
                  )}
                </span>
                {due.streak > 0 && (
                  <span className="today-streak" title={`${due.streak} due days in a row`}>
                    {due.streak}-day streak
                  </span>
                )}
              </label>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

interface HeadsUpProps {
  items: HeadsUpItem[]
  today: string
  onPostpone: (task: TaskRead) => void
  onComplete: (task: TaskRead) => void
}

/** Open tasks outside the three that need a decision today. */
function HeadsUp({ items, today, onPostpone, onComplete }: HeadsUpProps) {
  const { go } = useNavigation()
  return (
    <section className="panel" aria-labelledby="heads-up-heading">
      <div className="today-panel-head">
        <h2 id="heads-up-heading">Heads-up</h2>
      </div>
      {items.length === 0 ? (
        <p className="today-empty muted">Nothing needs you today.</p>
      ) : (
        <ul className="today-heads-up">
          {items.map((item) => (
            <li key={item.task.id} className={`today-alert ${item.kind}`}>
              <div className="grow">
                <p>{item.task.title}</p>
                <p className={item.kind === 'overdue' ? 'small loss' : item.kind === 'ready' ? 'small gain' : 'small muted'}>
                  {headsUpReason(item, today)}
                </p>
              </div>
              {item.kind === 'overdue' && (
                <button type="button" aria-label={`Postpone “${item.task.title}”`} onClick={() => onPostpone(item.task)}>
                  Postpone
                </button>
              )}
              {item.kind === 'ready' && (
                <button type="button" aria-label={`Complete “${item.task.title}”`} onClick={() => onComplete(item.task)}>
                  Complete
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      <div className="today-panel-foot">
        <button type="button" className="link" onClick={() => go('tasks')}>
          All tasks
        </button>
      </div>
    </section>
  )
}

function Chevron({ direction }: { direction: 'left' | 'right' }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={direction === 'left' ? 'm15 18-6-6 6-6' : 'm9 18 6-6-6-6'} />
    </svg>
  )
}
