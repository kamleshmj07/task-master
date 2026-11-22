import type { PostponeReason, PostponeResponse, TaskRead } from '@task-master/api-client'
import { type FormEvent, useState } from 'react'

import { api, errorMessage } from '@/api'
import { Modal } from '@/components/Modal'
import { REASONS } from '@/data'
import { addDays, todayIso } from '@/dates'

interface PostponeDialogProps {
  task: TaskRead
  onPostponed: (result: PostponeResponse) => void
  onClose: () => void
}

/** Pop-up asking why a task is being put off, then where it should go. */
export function PostponeDialog({ task, onPostponed, onClose }: PostponeDialogProps) {
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
    if (apiError || !data) {
      setError(errorMessage(apiError))
      return
    }
    onPostponed(data)
  }

  return (
    <Modal title="Why are you putting this off?" onClose={onClose}>
      <form className="stack" onSubmit={handleSubmit}>
        <p className="muted">“{task.title}”</p>
        <div className="reasons" role="group" aria-label="Reason">
          {REASONS.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              className={reason === value ? 'reason selected' : 'reason'}
              aria-pressed={reason === value}
              onClick={() => {
                setReason(value)
                setError(null)
              }}
            >
              {label}
            </button>
          ))}
        </div>
        {reason === 'other' && (
          <label>
            What's going on?
            <input required maxLength={280} value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
        )}
        <div className="row wrap-end">
          <label>
            New date
            <input
              type="date"
              required={!someday}
              disabled={someday}
              min={earliest}
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
            />
          </label>
          <label className="choice">
            <input type="checkbox" checked={someday} onChange={(e) => setSomeday(e.target.checked)} />
            Move to Someday instead
          </label>
        </div>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <div className="row">
          <button type="submit" className="primary">
            Postpone
          </button>
          <button type="button" onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </Modal>
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
    <aside className="card suggestion stack" aria-label="Suggested fix">
      <p className="eyebrow">Postponed · here's how to break the pattern</p>
      <h3>{suggestion.headline}</h3>
      <ul>
        {suggestion.actions.map((action) => (
          <li key={action}>{action}</li>
        ))}
      </ul>
      {suggestion.reflection && <p className="reflection">{suggestion.reflection}</p>}
      <div>
        <button type="button" onClick={onDismiss}>
          Got it
        </button>
      </div>
    </aside>
  )
}

function latest(a: string, b: string | null): string {
  return b !== null && b > a ? b : a
}
