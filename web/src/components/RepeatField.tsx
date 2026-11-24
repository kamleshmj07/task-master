import { Field, FieldGroup } from '@/components/Field'
import { type RepeatChoice, type RepeatDraft, weekdayOf } from '@/data'
import { WEEKDAYS } from '@/dates'

interface RepeatFieldProps {
  draft: RepeatDraft
  /** The task's due date: the first run, and the default day to repeat on. */
  dueDate: string
  onChange: (draft: RepeatDraft) => void
}

/** How a task repeats: not at all, daily, weekly on chosen days, or monthly. */
export function RepeatField({ draft, dueDate, onChange }: RepeatFieldProps) {
  const set = (patch: Partial<RepeatDraft>) => onChange({ ...draft, ...patch })

  function handleFrequency(frequency: RepeatChoice) {
    // Start from the due date's weekday or day of month, so one pick is enough.
    const defaults: Partial<RepeatDraft> = dueDate
      ? {
          weekdays: draft.weekdays.length > 0 ? draft.weekdays : [weekdayOf(dueDate)],
          dayOfMonth: draft.dayOfMonth || String(Number(dueDate.slice(8, 10))),
        }
      : {}
    set({ frequency, ...defaults })
  }

  function toggleWeekday(day: number) {
    const weekdays = draft.weekdays.includes(day)
      ? draft.weekdays.filter((d) => d !== day)
      : [...draft.weekdays, day]
    set({ weekdays })
  }

  return (
    <div className="stack-sm">
      <div className="grid">
        <Field
          label="Repeats"
          info="For recurring work toward a goal, like a daily run. Only the next run shows. Finishing or skipping it brings up the one after, and missed runs never pile up. Everyday chores belong in Routines."
        >
          {(id) => (
            <select id={id} value={draft.frequency} onChange={(e) => handleFrequency(e.target.value as RepeatChoice)}>
              <option value="none">Doesn't repeat</option>
              <option value="daily">Every day</option>
              <option value="weekly">Weekly, on chosen days</option>
              <option value="monthly">Monthly, on a day of the month</option>
            </select>
          )}
        </Field>
        {draft.frequency === 'monthly' && (
          <Field label="Day of month" info="On the 29th to 31st, shorter months use their last day.">
            {(id) => (
              <input
                id={id}
                type="number"
                min={1}
                max={31}
                required
                value={draft.dayOfMonth}
                onChange={(e) => set({ dayOfMonth: e.target.value })}
              />
            )}
          </Field>
        )}
        {draft.frequency !== 'none' && (
          <Field label="Repeat until" info="Optional. The last day a run can fall on. Leave it empty to keep repeating.">
            {(id) => (
              <input
                id={id}
                type="date"
                {...(dueDate ? { min: dueDate } : {})}
                value={draft.until}
                onChange={(e) => set({ until: e.target.value })}
              />
            )}
          </Field>
        )}
      </div>
      {draft.frequency === 'weekly' && (
        <FieldGroup label="On these days">
          <div className="row">
            {WEEKDAYS.map((label, day) => (
              <label key={label} className="choice day-choice">
                <input type="checkbox" checked={draft.weekdays.includes(day)} onChange={() => toggleWeekday(day)} />
                {label}
              </label>
            ))}
          </div>
        </FieldGroup>
      )}
    </div>
  )
}
