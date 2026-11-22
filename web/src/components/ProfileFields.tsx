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
      <label>
        Your name
        <input
          required
          maxLength={100}
          autoComplete="name"
          placeholder="What should we call you?"
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
        />
      </label>
      <label>
        <span>
          Timezone <span className="muted">· decides when your day starts</span>
        </span>
        <select required value={timezone} onChange={(e) => onTimezoneChange(e.target.value)}>
          {timezoneOptions(timezone).map((zone) => (
            <option key={zone} value={zone}>
              {zone.replaceAll('_', ' ')}
            </option>
          ))}
        </select>
      </label>
    </>
  )
}
