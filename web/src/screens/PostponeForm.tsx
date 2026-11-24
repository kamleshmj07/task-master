import type { PostponeReason, PostponeResponse, TaskRead } from '@task-master/api-client'
import { type FormEvent, useState } from 'react'

import { api, errorMessage } from '@/api'
import { Modal } from '@/components/Modal'
import { REASONS } from '@/data'
import { addDays, formatDay, quickDates, todayIso } from '@/dates'
import { useNavigation } from '@/navigation'
import { tipArticle } from '@/tips'

type Target = { kind: 'date'; date: string } | { kind: 'pick' } | { kind: 'someday' } | { kind: 'skip' }

interface PostponeDialogProps {
  task: TaskRead
  onPostponed: (result: PostponeResponse) => void
  onClose: () => void
}

/**
 * Pop-up asking why a task is being put off, then where it should go. A
 * repeating task can skip to its next run instead of going to Someday.
 */
export function PostponeDialog({ task, onPostponed, onClose }: PostponeDialogProps) {
  const repeating = task.repeat !== null
  const today = todayIso()
  const earliest = latest(today, task.due_date ? addDays(task.due_date, 1) : null)
  const chips = quickDates(today)
  const firstValid = chips.find((chip) => chip.date >= earliest)
  const [reason, setReason] = useState<PostponeReason | null>(null)
  const [target, setTarget] = useState<Target>(
    repeating ? { kind: 'skip' } : firstValid ? { kind: 'date', date: firstValid.date } : { kind: 'pick' },
  )
  const [picked, setPicked] = useState(earliest)
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)

  const toDate =
    target.kind === 'someday' || target.kind === 'skip' ? null : target.kind === 'pick' ? picked : target.date

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!reason) {
      setError('Pick a reason first.')
      return
    }
    const path = { params: { path: { task_id: task.id } } }
    const { data, error: apiError } =
      target.kind === 'skip'
        ? await api.POST('/tasks/{task_id}/skip', { ...path, body: { reason, note: note || null } })
        : await api.POST('/tasks/{task_id}/postpone', { ...path, body: { reason, to_date: toDate, note: note || null } })
    if (apiError || !data) {
      setError(errorMessage(apiError))
      return
    }
    onPostponed(data)
  }

  return (
    <Modal title="Why are you putting this off?" onClose={onClose}>
      <form className="stack" onSubmit={handleSubmit}>
        <p className="muted">
          “{task.title}”{task.due_date ? `, due ${formatDay(task.due_date)}` : ', no date yet'}
        </p>
        <div className="reasons" role="group" aria-label="Reason">
          {REASONS.map(({ value, label, hint, fix }) => (
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
              <span className="reason-label">{label}</span>
              <span className="reason-hint">{hint}</span>
              <span className="reason-fix">{fix}</span>
            </button>
          ))}
        </div>
        {reason === 'other' && (
          <label>
            What's going on?
            <input required maxLength={280} value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
        )}

        <div className="stack-sm">
          <p className="field-label" id="move-to">
            Move it to
          </p>
          <div className="chips" role="group" aria-labelledby="move-to">
            {chips.map((chip) => (
              <button
                key={chip.label}
                type="button"
                className="chip"
                disabled={chip.date < earliest}
                aria-pressed={target.kind === 'date' && target.date === chip.date}
                onClick={() => setTarget({ kind: 'date', date: chip.date })}
              >
                {chip.label}
              </button>
            ))}
            <button
              type="button"
              className="chip"
              aria-pressed={target.kind === 'pick'}
              onClick={() => setTarget({ kind: 'pick' })}
            >
              Pick a date…
            </button>
            {repeating ? (
              <button
                type="button"
                className="chip"
                aria-pressed={target.kind === 'skip'}
                onClick={() => setTarget({ kind: 'skip' })}
              >
                Skip to next run
              </button>
            ) : (
              <button
                type="button"
                className="chip"
                aria-pressed={target.kind === 'someday'}
                onClick={() => setTarget({ kind: 'someday' })}
              >
                Someday
              </button>
            )}
          </div>
          {target.kind === 'pick' && (
            <label>
              New date
              <input type="date" required min={earliest} value={picked} onChange={(e) => setPicked(e.target.value)} />
            </label>
          )}
          <p className="muted small" aria-live="polite">
            {target.kind === 'skip'
              ? 'This run is skipped. It moves to the next day the task repeats.'
              : toDate
                ? `New due date: ${formatDay(toDate)}`
                : 'It moves to Someday, with no date.'}
          </p>
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

const REASON_ICONS: Record<PostponeReason, string> = {
  stuck: 'M4 20h16M7 16l4-12 2 6 2-3 2 9',
  dreading: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm-3 13s1-2 3-2 3 2 3 2M9 9h.01M15 9h.01',
  blocked: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM5.6 5.6l12.8 12.8',
  other: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 5v5m0 3h.01',
}

interface TipDialogProps {
  result: PostponeResponse
  onDismiss: () => void
  /** Opens the task's steps, for fixes that start there. */
  onOpenSteps?: () => void
}

/**
 * Shown once after postponing: the fix for the reason given, and a way into
 * the full guide. It is not saved anywhere; it is gone once dismissed.
 */
export function TipDialog({ result, onDismiss, onOpenSteps }: TipDialogProps) {
  const { suggestion, postponement, task } = result
  const { go } = useNavigation()
  const [tried, setTried] = useState<string[]>([])
  const where = postponement.to_date ? formatDay(postponement.to_date) : 'Someday'
  const startsWithSteps = postponement.reason === 'stuck' || postponement.reason === 'dreading'
  const guide = tipArticle(postponement.reason)

  return (
    <Modal title={suggestion.headline} onClose={onDismiss}>
      <div className="tip-intro">
        <span className="coach-icon" aria-hidden="true">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d={REASON_ICONS[postponement.reason]} />
          </svg>
        </span>
        <p className="muted">
          Moved “{task.title}” to {where}. Try one of these before it comes back.
        </p>
      </div>
      <ul className="list tip-actions">
        {suggestion.actions.map((action) => (
          <li key={action}>
            <label className="choice">
              <input
                type="checkbox"
                checked={tried.includes(action)}
                onChange={() =>
                  setTried(tried.includes(action) ? tried.filter((a) => a !== action) : [...tried, action])
                }
              />
              {action}
            </label>
          </li>
        ))}
      </ul>
      {suggestion.reflection && (
        <p className="reflection tip-reflection" role="note">
          {suggestion.reflection}
        </p>
      )}
      {guide && (
        <div className="tip-guide">
          <p className="field-label">From the guide: {guide.title}</p>
          <p className="muted small">{guide.summary}</p>
          <div>
            <button
              type="button"
              className="link"
              onClick={() => {
                onDismiss()
                go('tips', { tip: postponement.reason })
              }}
            >
              Read the guide with examples
            </button>
          </div>
        </div>
      )}
      <div className="row">
        <button type="button" className="primary" onClick={onDismiss}>
          Got it
        </button>
        {startsWithSteps && onOpenSteps && (
          <button type="button" onClick={onOpenSteps}>
            Open steps
          </button>
        )}
      </div>
    </Modal>
  )
}

function latest(a: string, b: string | null): string {
  return b !== null && b > a ? b : a
}
