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

/** Icons for the phone's bottom tab bar (stroke paths on a 24px grid). */
const NAV_ICONS: Partial<Record<ScreenName, string>> = {
  today: 'M12 3v2M5.6 5.6l1.4 1.4M3 12h2M19 12h2M17 7l1.4-1.4M8 16a4 4 0 1 1 8 0M4 20h16',
  tasks: 'M4 7h3M4 12h3M4 17h3M10 7h10M10 12h10M10 17h6',
  routines: 'M21 12a9 9 0 1 1-3-6.7L21 8M21 3v5h-5',
  goals: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 4a5 5 0 1 0 0 10 5 5 0 0 0 0-10Z',
  tips: 'M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.5c.8.8 1 1.6 1 2.5h6c0-.9.2-1.7 1-2.5A6 6 0 0 0 12 3Z',
}

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
                <svg className="nav-icon" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d={NAV_ICONS[name] ?? ''} />
                </svg>
                <span>{SCREENS[name].label}</span>
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
