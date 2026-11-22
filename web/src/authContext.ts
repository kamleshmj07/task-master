import type { UserRead } from '@task-master/api-client'
import { createContext, useContext } from 'react'

/** Signed-in state and the actions that change it. */
export interface Auth {
  user: UserRead | null
  loading: boolean
  login: (email: string, password: string) => Promise<string | null>
  register: (email: string, password: string) => Promise<string | null>
  logout: () => Promise<void>
  setUser: (user: UserRead) => void
}

export const AuthContext = createContext<Auth | null>(null)

export function useAuth(): Auth {
  const auth = useContext(AuthContext)
  if (!auth) throw new Error('useAuth must be used inside <AuthProvider>')
  return auth
}
