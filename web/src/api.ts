import { createApiClient } from '@task-master/api-client'

/** Where the API lives. Use `localhost`, not `127.0.0.1`, so cookies work. */
export const API_URL: string =
  import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

let accessToken: string | null = null
let refreshing: Promise<boolean> | null = null

export function setAccessToken(token: string | null): void {
  accessToken = token
}

/**
 * Swap the HttpOnly refresh cookie for a new access token. Concurrent
 * callers share one request, because each refresh token works only once.
 */
export function refreshSession(): Promise<boolean> {
  refreshing ??= (async () => {
    try {
      const response = await fetch(`${API_URL}/auth/web/refresh`, {
        method: 'POST',
        credentials: 'include',
      })
      if (!response.ok) {
        setAccessToken(null)
        return false
      }
      const body = (await response.json()) as { access_token: string }
      setAccessToken(body.access_token)
      return true
    } finally {
      refreshing = null
    }
  })()
  return refreshing
}

/** Retry a request once with a fresh access token when it gets a 401. */
/**
 * Whether `url` is an auth endpoint, wherever the API lives: at the root
 * (`http://localhost:8000/auth/...`) or under a path (`/api/auth/...`).
 */
export function isAuthPath(url: string, apiUrl: string = API_URL): boolean {
  const base = new URL(apiUrl, 'https://placeholder.invalid').pathname.replace(/\/$/, '')
  return new URL(url, 'https://placeholder.invalid').pathname.startsWith(`${base}/auth/`)
}

export async function fetchWithRefresh(request: Request): Promise<Response> {
  const retry = request.clone()
  const response = await fetch(request)
  if (response.status !== 401 || isAuthPath(request.url) || !(await refreshSession())) {
    return response
  }
  retry.headers.set('Authorization', `Bearer ${accessToken ?? ''}`)
  return fetch(retry)
}

export const api = createApiClient({
  baseUrl: API_URL,
  getAccessToken: () => accessToken,
  credentials: 'include',
  fetch: fetchWithRefresh,
})

/** Turn a FastAPI error body into one readable sentence. */
export function errorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'detail' in error) {
    const { detail } = error as { detail: unknown }
    if (typeof detail === 'string') return humanize(detail)
    // fastapi-users errors: {"code": "...", "reason": "..."}
    if (typeof detail === 'object' && detail !== null && 'reason' in detail) {
      const { reason } = detail as { reason: unknown }
      if (typeof reason === 'string') return reason.endsWith('.') ? reason : `${reason}.`
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: unknown }
      if (typeof first.msg === 'string') return first.msg.replace(/^Value error, /, '')
    }
  }
  return 'Something went wrong. Please try again.'
}

const ERROR_CODES: Record<string, string> = {
  LOGIN_BAD_CREDENTIALS: 'Wrong email or password.',
  REGISTER_USER_ALREADY_EXISTS: 'An account with this email already exists.',
}

function humanize(detail: string): string {
  return ERROR_CODES[detail] ?? detail
}
