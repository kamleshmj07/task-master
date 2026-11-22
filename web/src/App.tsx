import { useEffect, useRef, useState } from 'react'

import { AuthProvider } from '@/auth'
import { useAuth } from '@/authContext'
import { NotificationBell } from '@/components/NotificationBell'
import { AuthScreen } from '@/screens/AuthScreen'
import { GoalsScreen } from '@/screens/GoalsScreen'
import { RoutinesScreen } from '@/screens/RoutinesScreen'
import { SettingsScreen } from '@/screens/SettingsScreen'
import { TasksScreen } from '@/screens/TasksScreen'
import { TodayScreen } from '@/screens/TodayScreen'
import { WelcomeDialog } from '@/screens/WelcomeDialog'

const SCREENS = {
  today: { label: 'Today', render: () => <TodayScreen /> },
  tasks: { label: 'Tasks', render: () => <TasksScreen /> },
  routines: { label: 'Routines', render: () => <RoutinesScreen /> },
  goals: { label: 'Goals', render: () => <GoalsScreen /> },
  settings: { label: 'Settings', render: () => <SettingsScreen /> },
} as const

type ScreenName = keyof typeof SCREENS
const NAV: ScreenName[] = ['today', 'tasks', 'routines', 'goals']

/** Application root: the session, then either sign-in or the main app. */
export function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  )
}

function Shell() {
  const { user, loading } = useAuth()
  const [screen, setScreen] = useState<ScreenName>('today')

  if (loading) return <p className="app muted">Loading…</p>
  if (!user) return <AuthScreen />

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <span className="brand">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <circle cx="12" cy="12" r="9" />
              <path d="m8 12 3 3 5-6" />
            </svg>
            Task Master
          </span>
          <nav aria-label="Main" className="nav">
            {NAV.map((name) => (
              <button
                key={name}
                type="button"
                aria-current={screen === name ? 'page' : undefined}
                onClick={() => setScreen(name)}
              >
                {SCREENS[name].label}
              </button>
            ))}
          </nav>
          <NotificationBell />
          <AccountMenu
            email={user.email}
            name={user.display_name ?? null}
            onSettings={() => setScreen('settings')}
          />
        </div>
      </header>
      <main className="app">{SCREENS[screen].render()}</main>
      {!user.display_name && <WelcomeDialog />}
    </div>
  )
}

interface AccountMenuProps {
  email: string
  name: string | null
  onSettings: () => void
}

function AccountMenu({ email, name, onSettings }: AccountMenuProps) {
  const { logout } = useAuth()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handleClick = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  return (
    <div
      className="account"
      ref={ref}
      onKeyDown={(event) => {
        if (event.key === 'Escape') setOpen(false)
      }}
    >
      <button type="button" className="ghost" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="avatar" aria-hidden="true">
          {initials(name ?? email)}
        </span>
        <span className="hide-sm">{name ?? email}</span>
      </button>
      {open && (
        <div className="menu" role="menu" aria-label="Account">
          <p className="muted small">Signed in as {email}</p>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false)
              onSettings()
            }}
          >
            Settings
          </button>
          <button type="button" role="menuitem" className="danger" onClick={() => void logout()}>
            Sign out
          </button>
        </div>
      )}
    </div>
  )
}

/** "Ada Lovelace" → "AL"; "ada@example.com" → "AD". */
function initials(text: string): string {
  const words = text.split(/[\s@.]+/).filter(Boolean)
  const letters = words.length > 1 ? `${words[0]?.[0] ?? ''}${words[1]?.[0] ?? ''}` : text.slice(0, 2)
  return letters.toUpperCase()
}
