import { type FormEvent, useState } from 'react'

import { useAuth } from '@/authContext'
import { InfoTip } from '@/components/InfoTip'

type Mode = 'login' | 'register'

/** Sign in, or create an account. */
export function AuthScreen() {
  const { login, register } = useAuth()
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    const action = mode === 'login' ? login : register
    setError(await action(email, password))
    setBusy(false)
  }

  const isLogin = mode === 'login'
  return (
    <main className="auth">
      <h1>Task Master</h1>
      <p className="muted">Goal-driven tasks that beat procrastination.</p>
      <form className="card stack" onSubmit={handleSubmit}>
        <h2>{isLogin ? 'Sign in' : 'Create account'}</h2>
        <label>
          Email
          <input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete={isLogin ? 'current-password' : 'new-password'}
            required
            minLength={isLogin ? undefined : 12}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {!isLogin && (
          <div className="row">
            <span className="muted small">Password rules</span>
            <InfoTip label="Password rules">
              At least 12 characters, and it must not contain the name part of your email.
            </InfoTip>
          </div>
        )}
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <button type="submit" className="primary" disabled={busy}>
          {isLogin ? 'Sign in' : 'Create account'}
        </button>
        <button
          type="button"
          className="link"
          onClick={() => {
            setMode(isLogin ? 'register' : 'login')
            setError(null)
          }}
        >
          {isLogin ? 'New here? Create an account' : 'Have an account? Sign in'}
        </button>
      </form>
    </main>
  )
}
