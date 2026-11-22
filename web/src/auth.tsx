import type { UserRead } from '@task-master/api-client'
import { type ReactNode, useCallback, useEffect, useMemo, useState } from 'react'

import { API_URL, api, errorMessage, refreshSession, setAccessToken } from '@/api'
import { AuthContext } from '@/authContext'

async function loadMe(): Promise<UserRead | null> {
  const { data } = await api.GET('/users/me')
  return data ?? null
}

/** Holds the session; restores it from the refresh cookie on page load. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserRead | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void (async () => {
      if (await refreshSession()) setUser(await loadMe())
      setLoading(false)
    })()
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const response = await fetch(`${API_URL}/auth/web/login`, {
      method: 'POST',
      credentials: 'include',
      body: new URLSearchParams({ username: email, password }),
    })
    const body: unknown = await response.json()
    if (!response.ok) return errorMessage(body)
    setAccessToken((body as { access_token: string }).access_token)
    setUser(await loadMe())
    return null
  }, [])

  const register = useCallback(
    async (email: string, password: string) => {
      const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
      const { error } = await api.POST('/auth/register', {
        body: { email, password, timezone },
      })
      if (error) return errorMessage(error)
      return login(email, password)
    },
    [login],
  )

  const logout = useCallback(async () => {
    await api.POST('/auth/web/logout')
    setAccessToken(null)
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, loading, login, register, logout, setUser }),
    [user, loading, login, register, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
