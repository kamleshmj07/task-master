import type { RoutineFrequency, RoutineRead } from '@task-master/api-client'
import { type FormEvent, useState } from 'react'

import { api, errorMessage } from '@/api'
import { addDays, formatDay, todayIso, WEEKDAYS } from '@/dates'
import { describeSchedule, loadGoals } from '@/data'
import { useResource } from '@/useResource'

async function loadRoutines(): Promise<RoutineRead[]> {
  const { data } = await api.GET('/routines', { params: { query: { limit: 100 } } })
  return data ?? []
}

/** Recurring routines: create and remove them. Tick them off on Today. */
export function RoutinesScreen() {
  const routines = useResource(loadRoutines)

  async function handleDelete(id: string) {
    await api.DELETE('/routines/{routine_id}', { params: { path: { routine_id: id } } })
    await routines.reload()
  }

  return (
    <section className="stack" aria-labelledby="routines-heading">
      <h2 id="routines-heading">Routines</h2>
      <p className="muted">
        Routines repeat on a schedule and are ticked off on Today. They are never
        postponed and never take a Top 3 slot.
      </p>
      <NewRoutineForm onCreated={() => void routines.reload()} />
      {routines.data?.length === 0 && <p className="muted">No routines yet.</p>}
      <ul className="list">
        {routines.data?.map((routine) => (
          <li key={routine.id} className="card item row">
            <div className="grow">
              <p className="title">{routine.title}</p>
              <p className="meta">
                {describeSchedule(routine)} · {formatDay(routine.start_date)} –{' '}
                {formatDay(routine.end_date)}
                {routine.estimate_minutes ? ` · ${routine.estimate_minutes} min` : ''}
              </p>
            </div>
            <button
              type="button"
              className="danger"
              aria-label={`Delete "${routine.title}"`}
              onClick={() => void handleDelete(routine.id)}
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}

function NewRoutineForm({ onCreated }: { onCreated: () => void }) {
  const goals = useResource(loadGoals)
  const [title, setTitle] = useState('')
  const [frequency, setFrequency] = useState<RoutineFrequency>('daily')
  const [weekdays, setWeekdays] = useState<number[]>([])
  const [dayOfMonth, setDayOfMonth] = useState('1')
  const [startDate, setStartDate] = useState(todayIso())
  const [endDate, setEndDate] = useState(addDays(todayIso(), 90))
  const [estimate, setEstimate] = useState('')
  const [goalId, setGoalId] = useState('')
  const [error, setError] = useState<string | null>(null)

  function toggleWeekday(day: number) {
    setWeekdays(weekdays.includes(day) ? weekdays.filter((d) => d !== day) : [...weekdays, day])
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const { error: apiError } = await api.POST('/routines', {
      body: {
        title,
        frequency,
        weekdays: frequency === 'weekly' ? weekdays : null,
        day_of_month: frequency === 'monthly' ? Number(dayOfMonth) : null,
        start_date: startDate,
        end_date: endDate,
        estimate_minutes: estimate ? Number(estimate) : null,
        goal_id: goalId || null,
      },
    })
    if (apiError) {
      setError(errorMessage(apiError))
      return
    }
    setTitle('')
    setWeekdays([])
    setError(null)
    onCreated()
  }

  return (
    <form className="card grid" onSubmit={handleSubmit} aria-label="New routine">
      <label>
        Routine
        <input required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label>
        Repeats
        <select
          value={frequency}
          onChange={(e) => setFrequency(e.target.value as RoutineFrequency)}
        >
          <option value="daily">Daily</option>
          <option value="weekly">Weekly, on chosen days</option>
          <option value="monthly">Monthly, on a day of the month</option>
        </select>
      </label>
      {frequency === 'weekly' && (
        <fieldset className="weekdays">
          <legend>On</legend>
          {WEEKDAYS.map((label, day) => (
            <label key={label} className="choice">
              <input
                type="checkbox"
                checked={weekdays.includes(day)}
                onChange={() => toggleWeekday(day)}
              />
              {label}
            </label>
          ))}
        </fieldset>
      )}
      {frequency === 'monthly' && (
        <label>
          Day of month
          <input
            type="number"
            min={1}
            max={31}
            required
            value={dayOfMonth}
            onChange={(e) => setDayOfMonth(e.target.value)}
          />
        </label>
      )}
      <label>
        Starts
        <input type="date" required value={startDate} onChange={(e) => setStartDate(e.target.value)} />
      </label>
      <label>
        Ends
        <input
          type="date"
          required
          min={startDate}
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
        />
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
        Goal
        <select value={goalId} onChange={(e) => setGoalId(e.target.value)}>
          <option value="">No goal</option>
          {goals.data?.map((goal) => (
            <option key={goal.id} value={goal.id}>
              {goal.title}
            </option>
          ))}
        </select>
      </label>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <button type="submit" className="primary">
        Add routine
      </button>
    </form>
  )
}
