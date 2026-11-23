import type { PostponeReason } from '@task-master/api-client'
import { type ReactNode, useEffect, useMemo, useRef, useState } from 'react'

import { AuthProvider } from '@/auth'
import { useAuth } from '@/authContext'
import { NotificationBell } from '@/components/NotificationBell'
import { type Navigation, NavigationContext, type ScreenName } from '@/navigation'
import { AuthScreen } from '@/screens/AuthScreen'
import { GoalsScreen } from '@/screens/GoalsScreen'
import { RoutinesScreen } from '@/screens/RoutinesScreen'
import { SettingsScreen } from '@/screens/SettingsScreen'
import { TasksScreen } from '@/screens/TasksScreen'
import { TipsScreen } from '@/screens/TipsScreen'
import { TodayScreen } from '@/screens/TodayScreen'
import { WelcomeDialog } from '@/screens/WelcomeDialog'

interface Route {
  screen: ScreenName
  tip?: PostponeReason | undefined
}

const SCREENS: Record<ScreenName, { label: string; render: (route: Route) => ReactNode }> = {
  today: { label: 'Today', render: () => <TodayScreen /> },
  tasks: { label: 'Tasks', render: () => <TasksScreen /> },
  routines: { label: 'Routines', render: () => <RoutinesScreen /> },
  goals: { label: 'Goals', render: () => <GoalsScreen /> },
  tips: { label: 'Tips', render: (route) => <TipsScreen key={route.tip ?? 'all'} initialTip={route.tip} /> },
  settings: { label: 'Settings', render: () => <SettingsScreen /> },
}

const NAV: ScreenName[] = ['today', 'tasks', 'routines', 'goals', 'tips']

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
  const [route, setRoute] = useState<Route>({ screen: 'today' })
  const navigation = useMemo<Navigation>(
    () => ({ go: (screen, options) => setRoute({ screen, tip: options?.tip }) }),
    [],
  )
  const screen = route.screen

  if (loading) return <p className="app muted">Loading…</p>
  if (!user) return <AuthScreen />

  return (
    <NavigationContext.Provider value={navigation}>
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <span className="brand">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
              <path d="M4 20h16" />
              <path d="M7 20 12 6l5 14" />
              <circle cx="12" cy="6" r="2" fill="currentColor" />
            </svg>
            Task Master
          </span>
          <nav aria-label="Main" className="nav">
            {NAV.map((name) => (
              <button
                key={name}
                type="button"
                aria-current={screen === name ? 'page' : undefined}
                onClick={() => navigation.go(name)}
              >
                {SCREENS[name].label}
              </button>
            ))}
          </nav>
          <NotificationBell />
          <AccountMenu
            email={user.email}
            name={user.display_name ?? null}
            onSettings={() => navigation.go('settings')}
          />
        </div>
      </header>
      <main className="app">{SCREENS[screen].render(route)}</main>
      {!user.display_name && <WelcomeDialog />}
    </div>
    </NavigationContext.Provider>
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
