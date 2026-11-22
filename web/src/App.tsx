import { useState } from 'react'

import { AuthProvider } from '@/auth'
import { useAuth } from '@/authContext'
import { AuthScreen } from '@/screens/AuthScreen'
import { GoalsScreen } from '@/screens/GoalsScreen'
import { RoutinesScreen } from '@/screens/RoutinesScreen'
import { SettingsScreen } from '@/screens/SettingsScreen'
import { TasksScreen } from '@/screens/TasksScreen'
import { TodayScreen } from '@/screens/TodayScreen'

const SCREENS = {
  today: { label: 'Today', render: () => <TodayScreen /> },
  tasks: { label: 'Tasks', render: () => <TasksScreen /> },
  routines: { label: 'Routines', render: () => <RoutinesScreen /> },
  goals: { label: 'Goals', render: () => <GoalsScreen /> },
  settings: { label: 'Settings', render: () => <SettingsScreen /> },
} as const

type ScreenName = keyof typeof SCREENS

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
    <div className="app">
      <header className="row between">
        <h1>Task Master</h1>
        <nav aria-label="Main">
          {(Object.keys(SCREENS) as ScreenName[]).map((name) => (
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
      </header>
      <main>{SCREENS[screen].render()}</main>
    </div>
  )
}
