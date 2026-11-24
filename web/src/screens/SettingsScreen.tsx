import { type FormEvent, useState } from 'react'

import { api, errorMessage } from '@/api'
import { useAuth } from '@/authContext'
import { Field } from '@/components/Field'
import { Modal } from '@/components/Modal'
import { PasswordInput } from '@/components/PasswordInput'
import { ProfileFields } from '@/components/ProfileFields'

/** Profile details, password, and the option to delete the account. */
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

      <ChangePasswordForm />

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

const MIN_PASSWORD_LENGTH = 12
const MAX_PASSWORD_LENGTH = 128

/**
 * Change the password, confirming the current one. The API then signs the
 * account out everywhere, this device included, so it ends with signing in.
 */
function ChangePasswordForm() {
  const { logout } = useAuth()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [changed, setChanged] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (next !== confirm) {
      setError('The new passwords do not match.')
      return
    }
    if (next === current) {
      setError('Choose a password different from the current one.')
      return
    }
    setBusy(true)
    const { error: apiError } = await api.PATCH('/users/me', {
      body: { password: next, current_password: current },
    })
    setBusy(false)
    if (apiError) {
      setError(errorMessage(apiError))
      return
    }
    setError(null)
    setChanged(true)
  }

  return (
    <form className="card stack" onSubmit={handleSubmit} aria-labelledby="password-heading">
      <h2 id="password-heading">Change password</h2>
      <div className="grid">
        <Field label="Current password">
          {(id) => (
            <PasswordInput
              id={id}
              what="current password"
              required
              autoComplete="current-password"
              maxLength={MAX_PASSWORD_LENGTH}
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
            />
          )}
        </Field>
        <Field
          label="New password"
          info={`${MIN_PASSWORD_LENGTH} to ${MAX_PASSWORD_LENGTH} characters, without your email name. A few unrelated words make a strong one.`}
        >
          {(id) => (
            <PasswordInput
              id={id}
              what="new password"
              required
              autoComplete="new-password"
              minLength={MIN_PASSWORD_LENGTH}
              maxLength={MAX_PASSWORD_LENGTH}
              value={next}
              onChange={(e) => setNext(e.target.value)}
            />
          )}
        </Field>
        <Field label="Confirm new password">
          {(id) => (
            <PasswordInput
              id={id}
              what="confirmed password"
              required
              autoComplete="new-password"
              maxLength={MAX_PASSWORD_LENGTH}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          )}
        </Field>
      </div>
      <p className="muted small">Changing it signs you out on every device, this one included.</p>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <div>
        <button type="submit" className="primary" disabled={busy}>
          Change password
        </button>
      </div>
      {changed && (
        <Modal title="Password changed" onClose={() => void logout()}>
          <p>You are signed out everywhere. Sign in again with your new password.</p>
          <div className="row">
            <button type="button" className="primary" onClick={() => void logout()}>
              Sign in again
            </button>
          </div>
        </Modal>
      )}
    </form>
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
        <Field label="Password">
          {(id) => (
            <PasswordInput
              id={id}
              required
              autoComplete="current-password"
              maxLength={128}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          )}
        </Field>
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
