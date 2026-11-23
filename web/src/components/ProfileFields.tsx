import { Field } from '@/components/Field'
import { timezoneOptions } from '@/dates'

interface ProfileFieldsProps {
  name: string
  timezone: string
  onNameChange: (name: string) => void
  onTimezoneChange: (timezone: string) => void
}

/** The minimum we ask about a user: what to call them, and their timezone. */
export function ProfileFields({ name, timezone, onNameChange, onTimezoneChange }: ProfileFieldsProps) {
  return (
    <>
      <Field label="Your name">
        {(id) => (
          <input
            id={id}
            required
            maxLength={100}
            autoComplete="name"
            placeholder="What should we call you?"
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
          />
        )}
      </Field>
      <Field label="Timezone" info="Decides when your day starts and ends, so Today, due dates and routine ticks match your local time.">
        {(id) => (
          <select id={id} required value={timezone} onChange={(e) => onTimezoneChange(e.target.value)}>
            {timezoneOptions(timezone).map((zone) => (
              <option key={zone} value={zone}>
                {zone.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        )}
      </Field>
    </>
  )
}
