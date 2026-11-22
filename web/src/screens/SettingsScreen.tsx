import { type FormEvent, useState } from 'react'

import { api, errorMessage } from '@/api'
import { useAuth } from '@/authContext'

/** Account settings: the timezone that decides what "today" means. */
export function SettingsScreen() {
  const { user, setUser } = useAuth()
  const [timezone, setTimezone] = useState(user?.timezone ?? 'UTC')
  const [message, setMessage] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const { data, error } = await api.PATCH('/users/me', { body: { timezone } })
    if (error || !data) {
      setMessage(errorMessage(error))
      return
    }
    setUser(data)
    setMessage('Saved.')
  }

  return (
    <section className="stack" aria-labelledby="settings-heading">
      <h1 id="settings-heading">Settings</h1>
      <p className="muted">Signed in as {user?.email}</p>
      <form className="card grid" onSubmit={handleSubmit} aria-label="Settings">
        <label>
          Timezone
          <input required value={timezone} onChange={(e) => setTimezone(e.target.value)} />
        </label>
        {message && <p role="status">{message}</p>}
        <button type="submit" className="primary">
          Save
        </button>
      </form>
    </section>
  )
}
