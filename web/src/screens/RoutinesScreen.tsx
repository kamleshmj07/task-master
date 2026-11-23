import type { RoutineCreate, RoutineFrequency, RoutineRead } from '@task-master/api-client'
import { type FormEvent, useState } from 'react'

import { api, errorMessage } from '@/api'
import { Field, FieldGroup } from '@/components/Field'
import { Modal } from '@/components/Modal'
import { describeSchedule, loadGoals } from '@/data'
import { addDays, formatDay, todayIso, WEEKDAYS } from '@/dates'
import { useResource } from '@/useResource'

async function loadRoutines(): Promise<RoutineRead[]> {
  const { data } = await api.GET('/routines', { params: { query: { limit: 100 } } })
  return data ?? []
}

/** Recurring routines: create, edit and remove them. Tick them off on Today. */
export function RoutinesScreen() {
  const routines = useResource(loadRoutines)
  const [editing, setEditing] = useState<RoutineRead | null>(null)
  const [deleting, setDeleting] = useState<RoutineRead | null>(null)

  async function handleDelete(routine: RoutineRead) {
    await api.DELETE('/routines/{routine_id}', { params: { path: { routine_id: routine.id } } })
    setDeleting(null)
    await routines.reload()
  }

  return (
    <section className="stack-lg" aria-labelledby="routines-heading">
      <div>
        <h1 id="routines-heading" className="page-title">
          Routines
        </h1>
        <p className="muted lede">
          Routines repeat on a schedule and are ticked off on Today. They are never postponed and
          never take a Top 3 slot.
        </p>
      </div>

      <section className="card stack" aria-labelledby="new-routine-heading">
        <h2 id="new-routine-heading">New routine</h2>
        <RoutineForm submitLabel="Add routine" onSaved={() => void routines.reload()} />
      </section>

      {routines.data?.length === 0 && (
        <div className="panel empty">
          <p className="title">No routines yet</p>
          <p className="muted">Add one above, then tick it off each day on Today.</p>
        </div>
      )}
      {routines.data && routines.data.length > 0 && (
        <ul className="panel plain-list">
          {routines.data.map((routine) => (
            <li key={routine.id} className="list-row">
              <div className="grow">
                <p className="title">{routine.title}</p>
                <p className="meta">
                  {describeSchedule(routine)}, from {formatDay(routine.start_date)} to{' '}
                  {formatDay(routine.end_date)}
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
      )}

      {editing && (
        <Modal title="Edit routine" onClose={() => setEditing(null)}>
          <RoutineForm
            routine={editing}
            submitLabel="Save changes"
            onSaved={() => {
              setEditing(null)
              void routines.reload()
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

interface RoutineFormProps {
  /** The routine to edit; leave out to create a new one. */
  routine?: RoutineRead
  submitLabel: string
  onSaved: () => void
  onCancel?: () => void
}

/** Create or edit a routine: what, how often, between which dates, toward which goal. */
function RoutineForm({ routine, submitLabel, onSaved, onCancel }: RoutineFormProps) {
  const goals = useResource(loadGoals)
  const [title, setTitle] = useState(routine?.title ?? '')
  const [frequency, setFrequency] = useState<RoutineFrequency>(routine?.frequency ?? 'daily')
  const [weekdays, setWeekdays] = useState<number[]>(routine?.weekdays ?? [])
  const [dayOfMonth, setDayOfMonth] = useState(String(routine?.day_of_month ?? 1))
  const [startDate, setStartDate] = useState(routine?.start_date ?? todayIso())
  const [endDate, setEndDate] = useState(routine?.end_date ?? addDays(todayIso(), 90))
  const [goalId, setGoalId] = useState(routine?.goal_id ?? '')
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
      goal_id: goalId || null,
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
        <Field label="Goal">
          {(id) => (
            <select id={id} value={goalId} onChange={(e) => setGoalId(e.target.value)}>
              <option value="">No goal</option>
              {goals.data?.map((goal) => (
                <option key={goal.id} value={goal.id}>
                  {goal.title}
                </option>
              ))}
            </select>
          )}
        </Field>
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
