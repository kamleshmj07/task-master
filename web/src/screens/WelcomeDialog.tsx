import { type FormEvent, useState } from 'react'

import { api, errorMessage } from '@/api'
import { useAuth } from '@/authContext'
import { ProfileFields } from '@/components/ProfileFields'
import { browserTimezone } from '@/dates'

/**
 * Shown on first sign-in, until the user has a name: the bare minimum we
 * need before planning starts. It cannot be dismissed without saving.
 */
export function WelcomeDialog() {
  const { user, setUser } = useAuth()
  const [name, setName] = useState('')
  const [timezone, setTimezone] = useState(
    user?.timezone && user.timezone !== 'UTC' ? user.timezone : browserTimezone(),
  )
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const { data, error: apiError } = await api.PATCH('/users/me', {
      body: { display_name: name, timezone },
    })
    if (apiError || !data) {
      setError(errorMessage(apiError))
      return
    }
    setUser(data)
  }

  return (
    <div className="overlay">
      <form
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="welcome-title"
        onSubmit={handleSubmit}
      >
        <h2 id="welcome-title">Welcome to Task Master</h2>
        <p className="muted">Two quick things before you start. You can change them later in Settings.</p>
        <ProfileFields name={name} timezone={timezone} onNameChange={setName} onTimezoneChange={setTimezone} />
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <div>
          <button type="submit" className="primary large">
            Get started
          </button>
        </div>
      </form>
    </div>
  )
}
