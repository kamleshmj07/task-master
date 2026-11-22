import type { PostponeReason, PostponeResponse, TaskRead } from '@task-master/api-client'
import { type FormEvent, useState } from 'react'

import { api, errorMessage } from '@/api'
import { REASONS } from '@/data'
import { addDays, todayIso } from '@/dates'

interface PostponeFormProps {
  task: TaskRead
  onPostponed: (result: PostponeResponse) => void
  onCancel: () => void
}

/** Ask why a task is being put off, then move it later or to Someday. */
export function PostponeForm({ task, onPostponed, onCancel }: PostponeFormProps) {
  const earliest = latest(todayIso(), task.due_date ? addDays(task.due_date, 1) : null)
  const [reason, setReason] = useState<PostponeReason | null>(null)
  const [toDate, setToDate] = useState(earliest)
  const [someday, setSomeday] = useState(false)
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!reason) {
      setError('Pick a reason first.')
      return
    }
    const { data, error: apiError } = await api.POST('/tasks/{task_id}/postpone', {
      params: { path: { task_id: task.id } },
      body: { reason, to_date: someday ? null : toDate, note: note || null },
    })
    if (apiError) {
      setError(errorMessage(apiError))
      return
    }
    onPostponed(data)
  }

  return (
    <form className="postpone stack" onSubmit={handleSubmit}>
      <fieldset>
        <legend>Why are you putting this off?</legend>
        {REASONS.map(({ value, label }) => (
          <label key={value} className="choice">
            <input
              type="radio"
              name={`reason-${task.id}`}
              value={value}
              checked={reason === value}
              onChange={() => setReason(value)}
            />
            {label}
          </label>
        ))}
      </fieldset>
      {reason === 'other' && (
        <label>
          What's going on?
          <input
            required
            maxLength={280}
            value={note}
            onChange={(event) => setNote(event.target.value)}
          />
        </label>
      )}
      <label className="choice">
        <input
          type="checkbox"
          checked={someday}
          onChange={(event) => setSomeday(event.target.checked)}
        />
        Move to Someday (no date)
      </label>
      {!someday && (
        <label>
          New date
          <input
            type="date"
            required
            min={earliest}
            value={toDate}
            onChange={(event) => setToDate(event.target.value)}
          />
        </label>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <div className="row">
        <button type="submit" className="primary">
          Postpone
        </button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  )
}

/** The fix suggested after postponing. */
export function SuggestionCard({
  result,
  onDismiss,
}: {
  result: PostponeResponse
  onDismiss: () => void
}) {
  const { suggestion } = result
  return (
    <aside className="card suggestion" aria-label="Suggested fix">
      <h3>{suggestion.headline}</h3>
      <ul>
        {suggestion.actions.map((action) => (
          <li key={action}>{action}</li>
        ))}
      </ul>
      {suggestion.reflection && <p className="reflection">{suggestion.reflection}</p>}
      <button type="button" onClick={onDismiss}>
        Got it
      </button>
    </aside>
  )
}

function latest(a: string, b: string | null): string {
  return b !== null && b > a ? b : a
}
