import type { DueRoutine, RoutineCreate, RoutineFrequency, RoutineRead } from '@task-master/api-client'
import { type FormEvent, useState } from 'react'

import { api, errorMessage } from '@/api'
import { EmptyState } from '@/components/EmptyState'
import { Field, FieldGroup } from '@/components/Field'
import { Modal } from '@/components/Modal'
import { TimeLimitField } from '@/components/TimeLimitField'
import {
  describeSchedule,
  fromMinutes,
  plural,
  timeLimitLabel,
  type TimeUnit,
  toMinutes,
  weekSummary,
} from '@/data'
import { addDays, formatDay, todayIso, WEEKDAYS } from '@/dates'
import { focusFormUnder } from '@/emptyStates'
import { useResource } from '@/useResource'

async function loadRoutines(): Promise<RoutineRead[]> {
  const { data } = await api.GET('/routines', { params: { query: { limit: 100 } } })
  return data ?? []
}

async function loadDueToday(): Promise<DueRoutine[]> {
  const { data } = await api.GET('/routines/due')
  return data ?? []
}

/** Recurring routines: tick off today's, see the last week, and manage them all. */
export function RoutinesScreen() {
  const routines = useResource(loadRoutines)
  const due = useResource(loadDueToday)
  const [editing, setEditing] = useState<RoutineRead | null>(null)
  const [deleting, setDeleting] = useState<RoutineRead | null>(null)

  function reloadAll() {
    void routines.reload()
    void due.reload()
  }

  async function handleDelete(routine: RoutineRead) {
    await api.DELETE('/routines/{routine_id}', { params: { path: { routine_id: routine.id } } })
    setDeleting(null)
    reloadAll()
  }

  return (
    <section className="stack-lg" aria-labelledby="routines-heading">
      <div>
        <h1 id="routines-heading" className="page-title">
          Routines
        </h1>
        <p className="muted lede">
          Everyday chores that repeat on a schedule, ticked off on Today. They stand alone: no goal,
          no steps, never postponed and never in the Top 3.
        </p>
      </div>

      <section className="card stack" aria-labelledby="new-routine-heading">
        <h2 id="new-routine-heading">New routine</h2>
        <RoutineForm submitLabel="Add routine" onSaved={reloadAll} />
      </section>

      {due.data && due.data.length > 0 && <DueToday routines={due.data} onChanged={() => void due.reload()} />}

      {routines.data?.length === 0 && (
        <EmptyState
          icon="routines"
          title="No routines yet"
          actionLabel="New routine"
          onAction={() => focusFormUnder('new-routine-heading')}
        >
          The small things you do on a schedule: a walk, vitamins, watering the plants. Every tick grows a
          streak.
        </EmptyState>
      )}
      {routines.data && routines.data.length > 0 && (
        <section className="stack-sm" aria-labelledby="all-routines-heading">
        <h2 id="all-routines-heading" className="group-head">
          All routines <span className="group-count">{routines.data.length}</span>
        </h2>
        <ul className="panel plain-list">
          {routines.data.map((routine) => (
            <li key={routine.id} className="list-row">
              <div className="grow">
                <p className="title">{routine.title}</p>
                <p className="meta">
                  {describeSchedule(routine)}, from {formatDay(routine.start_date)} to{' '}
                  {formatDay(routine.end_date)}
                  {routine.time_limit_minutes ? `, ${timeLimitLabel(routine.time_limit_minutes)} each time` : ''}
                </p>
              </div>
              <button type="button" aria-label={`Edit “${routine.title}”`} onClick={() => setEditing(routine)}>
                Edit
              </button>
              <button
                type="button"
                className="ghost danger"
                aria-label={`Delete “${routine.title}”`}
                onClick={() => setDeleting(routine)}
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
        </section>
      )}

      {editing && (
        <Modal title="Edit routine" onClose={() => setEditing(null)}>
          <RoutineForm
            routine={editing}
            submitLabel="Save changes"
            onSaved={() => {
              setEditing(null)
              reloadAll()
            }}
            onCancel={() => setEditing(null)}
          />
        </Modal>
      )}

      {deleting && (
        <Modal title="Delete this routine?" onClose={() => setDeleting(null)}>
          <p>
            “{deleting.title}” and its whole history of ticks will be deleted. This cannot be
            undone.
          </p>
          <div className="row">
            <button type="button" className="danger solid" onClick={() => void handleDelete(deleting)}>
              Delete routine
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

interface DueTodayProps {
  routines: DueRoutine[]
  onChanged: () => void
}

/** Today's routines: a big tick each, the last seven days, and the streak. */
function DueToday({ routines, onChanged }: DueTodayProps) {
  const today = todayIso()
  const done = routines.filter((due) => due.done).length

  async function handleToggle({ routine, done: isDone }: DueRoutine) {
    const params = { path: { routine_id: routine.id, day: today } }
    if (isDone) await api.DELETE('/routines/{routine_id}/completions/{day}', { params })
    else await api.PUT('/routines/{routine_id}/completions/{day}', { params })
    onChanged()
  }

  return (
    <section className="stack-sm" aria-labelledby="due-today-heading">
      <h2 id="due-today-heading" className="group-head between">
        Due today
        <span className={done === routines.length ? 'gain small' : 'muted small'}>
          {done} of {routines.length} done
        </span>
      </h2>
      <ul className="panel plain-list">
        {routines.map((due) => (
          <li key={due.routine.id} className="routine-due">
            <button
              type="button"
              className="routine-tick"
              aria-pressed={due.done}
              aria-label={`Done today: ${due.routine.title}`}
              onClick={() => void handleToggle(due)}
            >
              {due.done && <TickIcon />}
            </button>
            <div className="grow">
              <p className="title">{due.routine.title}</p>
              <p className="meta">
                {describeSchedule(due.routine)}
                {due.routine.time_limit_minutes ? `, ${timeLimitLabel(due.routine.time_limit_minutes)}` : ''}
              </p>
            </div>
            <span className="week-dots" role="img" aria-label={weekSummary(due.recent_days)}>
              {due.recent_days.map((mark, index) => (
                <span key={index} className={`week-dot ${mark}`} />
              ))}
            </span>
            <span className={due.streak > 0 ? 'routine-streak lit' : 'routine-streak'}>
              {due.streak > 0 ? `${plural(due.streak, 'day')} in a row` : 'No streak yet'}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}

function TickIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M5 12.5l4.5 4.5L19 7.5" />
    </svg>
  )
}

interface RoutineFormProps {
  /** The routine to edit; leave out to create a new one. */
  routine?: RoutineRead
  submitLabel: string
  onSaved: () => void
  onCancel?: () => void
}

/** Create or edit a routine: what, how often, between which dates, how long each time. */
function RoutineForm({ routine, submitLabel, onSaved, onCancel }: RoutineFormProps) {
  const [title, setTitle] = useState(routine?.title ?? '')
  const [frequency, setFrequency] = useState<RoutineFrequency>(routine?.frequency ?? 'daily')
  const [weekdays, setWeekdays] = useState<number[]>(routine?.weekdays ?? [])
  const [dayOfMonth, setDayOfMonth] = useState(String(routine?.day_of_month ?? 1))
  const [startDate, setStartDate] = useState(routine?.start_date ?? todayIso())
  const [endDate, setEndDate] = useState(routine?.end_date ?? addDays(todayIso(), 90))
  const initialLimit = fromMinutes(routine?.time_limit_minutes ?? null)
  const [limitAmount, setLimitAmount] = useState(initialLimit.amount)
  const [limitUnit, setLimitUnit] = useState<TimeUnit>(initialLimit.unit)
  const [error, setError] = useState<string | null>(null)

  function toggleWeekday(day: number) {
    setWeekdays(weekdays.includes(day) ? weekdays.filter((d) => d !== day) : [...weekdays, day])
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const body: RoutineCreate = {
      title,
      frequency,
      weekdays: frequency === 'weekly' ? weekdays : null,
      day_of_month: frequency === 'monthly' ? Number(dayOfMonth) : null,
      start_date: startDate,
      end_date: endDate,
      time_limit_minutes: toMinutes(limitAmount, limitUnit),
    }
    const { error: apiError } = routine
      ? await api.PATCH('/routines/{routine_id}', { params: { path: { routine_id: routine.id } }, body })
      : await api.POST('/routines', { body })
    if (apiError) {
      setError(errorMessage(apiError))
      return
    }
    if (!routine) {
      setTitle('')
      setWeekdays([])
    }
    setError(null)
    onSaved()
  }

  return (
    <form className="stack" onSubmit={handleSubmit} aria-label={routine ? 'Edit routine' : 'New routine'}>
      <div className="grid">
        <Field label="Routine">
          {(id) => <input id={id} required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />}
        </Field>
        <Field
          label="Repeats"
          info="Daily, weekly on the days you choose, or monthly on a day of the month. A monthly routine on the 29th to 31st falls on the last day of shorter months."
        >
          {(id) => (
            <select id={id} value={frequency} onChange={(e) => setFrequency(e.target.value as RoutineFrequency)}>
              <option value="daily">Daily</option>
              <option value="weekly">Weekly, on chosen days</option>
              <option value="monthly">Monthly, on a day of the month</option>
            </select>
          )}
        </Field>
        {frequency === 'monthly' && (
          <Field label="Day of month">
            {(id) => (
              <input
                id={id}
                type="number"
                min={1}
                max={31}
                required
                value={dayOfMonth}
                onChange={(e) => setDayOfMonth(e.target.value)}
              />
            )}
          </Field>
        )}
        <Field label="Starts">
          {(id) => <input id={id} type="date" required value={startDate} onChange={(e) => setStartDate(e.target.value)} />}
        </Field>
        <Field label="Ends" info="Every routine has an end date. You can always extend it later.">
          {(id) => (
            <input
              id={id}
              type="date"
              required
              min={startDate}
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          )}
        </Field>
        <TimeLimitField
          amount={limitAmount}
          unit={limitUnit}
          onAmountChange={setLimitAmount}
          onUnitChange={setLimitUnit}
          info="Optional. The most time to spend each time the routine is due."
        />
      </div>
      {frequency === 'weekly' && (
        <FieldGroup label="On these days">
          <div className="row">
            {WEEKDAYS.map((label, day) => (
              <label key={label} className="choice day-choice">
                <input type="checkbox" checked={weekdays.includes(day)} onChange={() => toggleWeekday(day)} />
                {label}
              </label>
            ))}
          </div>
        </FieldGroup>
      )}
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
