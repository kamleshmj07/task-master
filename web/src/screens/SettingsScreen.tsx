import { type FormEvent, useState } from 'react'

import { api, errorMessage } from '@/api'
import { useAuth } from '@/authContext'

/** Account settings that shape planning: timezone and daily capacity. */
export function SettingsScreen() {
  const { user, setUser, logout } = useAuth()
  const [timezone, setTimezone] = useState(user?.timezone ?? 'UTC')
  const [capacity, setCapacity] = useState(String(user?.daily_capacity_minutes ?? 480))
  const [message, setMessage] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const { data, error } = await api.PATCH('/users/me', {
      body: { timezone, daily_capacity_minutes: Number(capacity) },
    })
    if (error || !data) {
      setMessage(errorMessage(error))
      return
    }
    setUser(data)
    setMessage('Saved.')
  }

  return (
    <section className="stack" aria-labelledby="settings-heading">
      <h2 id="settings-heading">Settings</h2>
      <p className="muted">Signed in as {user?.email}</p>
      <form className="card grid" onSubmit={handleSubmit} aria-label="Settings">
        <label>
          Timezone
          <input required value={timezone} onChange={(e) => setTimezone(e.target.value)} />
        </label>
        <label>
          Daily capacity (min)
          <input
            type="number"
            min={1}
            max={1440}
            required
            value={capacity}
            onChange={(e) => setCapacity(e.target.value)}
          />
        </label>
        {message && <p role="status">{message}</p>}
        <button type="submit" className="primary">
          Save
        </button>
      </form>
      <button type="button" onClick={() => void logout()}>
        Sign out
      </button>
    </section>
  )
}
