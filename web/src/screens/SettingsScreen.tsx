import { type FormEvent, useState } from 'react'

import { api, errorMessage } from '@/api'
import { useAuth } from '@/authContext'
import { Modal } from '@/components/Modal'
import { ProfileFields } from '@/components/ProfileFields'

/** Profile details, and the option to delete the account. */
export function SettingsScreen() {
  const { user, setUser } = useAuth()
  const [name, setName] = useState(user?.display_name ?? '')
  const [timezone, setTimezone] = useState(user?.timezone ?? 'UTC')
  const [message, setMessage] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const { data, error } = await api.PATCH('/users/me', {
      body: { display_name: name, timezone },
    })
    if (error || !data) {
      setMessage(errorMessage(error))
      return
    }
    setUser(data)
    setMessage('Saved.')
  }

  return (
    <section className="stack-lg" aria-labelledby="settings-heading">
      <h1 id="settings-heading">Settings</h1>

      <form className="card stack" onSubmit={handleSubmit} aria-labelledby="profile-heading">
        <h2 id="profile-heading">Profile</h2>
        <div className="grid">
          <ProfileFields name={name} timezone={timezone} onNameChange={setName} onTimezoneChange={setTimezone} />
          <label>
            Email
            <input value={user?.email ?? ''} readOnly aria-readonly="true" />
          </label>
        </div>
        {message && <p role="status">{message}</p>}
        <div>
          <button type="submit" className="primary">
            Save
          </button>
        </div>
      </form>

      <section className="card danger-zone stack" aria-labelledby="danger-heading">
        <h2 id="danger-heading">Delete account</h2>
        <p className="muted">
          Permanently deletes your account and everything in it: goals, tasks, steps, routines, plans and
          notifications. This cannot be undone.
        </p>
        <div>
          <button type="button" className="danger" onClick={() => setDeleting(true)}>
            Delete account…
          </button>
        </div>
      </section>

      {deleting && <DeleteAccountDialog onClose={() => setDeleting(false)} />}
    </section>
  )
}

function DeleteAccountDialog({ onClose }: { onClose: () => void }) {
  const { deleteAccount } = useAuth()
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    const failure = await deleteAccount(password)
    setBusy(false)
    if (failure) setError(failure)
  }

  return (
    <Modal title="Delete your account?" onClose={onClose}>
      <form className="stack" onSubmit={handleSubmit}>
        <p>
          Everything you have in Task Master will be deleted straight away. Enter your password to
          confirm.
        </p>
        <label>
          Password
          <input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <div className="row">
          <button type="submit" className="danger solid" disabled={busy}>
            Delete everything
          </button>
          <button type="button" onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  )
}
