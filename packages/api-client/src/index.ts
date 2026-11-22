import createClient, { type Middleware } from 'openapi-fetch'

import type { components, paths } from './schema'

export type { components, paths }
type Schemas = components['schemas']
export type UserRead = Schemas['UserRead']
export type AccessTokenResponse = Schemas['AccessTokenResponse']
export type TokenPairResponse = Schemas['TokenPairResponse']
export type GoalRead = Schemas['GoalRead']
export type GoalStatus = Schemas['GoalStatus']
export type TaskRead = Schemas['TaskRead']
export type TaskCreate = Schemas['TaskCreate']
export type PostponeReason = Schemas['PostponeReason']
export type PostponeResponse = Schemas['PostponeResponse']
export type RoutineRead = Schemas['RoutineRead']
export type RoutineCreate = Schemas['RoutineCreate']
export type RoutineFrequency = Schemas['RoutineFrequency']
export type DueRoutine = Schemas['DueRoutine']
export type PlanRead = Schemas['PlanRead']

/** How a client reaches the API and finds its current access token. */
export interface ApiClientOptions {
  baseUrl: string
  /** Returns the in-memory access token, or null when logged out. */
  getAccessToken: () => string | null
  /**
   * `'include'` on web, so the browser sends the refresh cookie to
   * `/auth/web/*`. Mobile keeps its refresh token itself and omits this.
   */
  credentials?: RequestCredentials
  fetch?: (request: Request) => Promise<Response>
}

/** Typed API client shared by the web and mobile apps. */
export function createApiClient(options: ApiClientOptions) {
  const client = createClient<paths>({
    baseUrl: options.baseUrl,
    ...(options.credentials ? { credentials: options.credentials } : {}),
    ...(options.fetch ? { fetch: options.fetch } : {}),
  })
  client.use(bearerAuth(options.getAccessToken))
  return client
}

export type ApiClient = ReturnType<typeof createApiClient>

/** Attach `Authorization: Bearer <token>` whenever a token is available. */
export function bearerAuth(getAccessToken: () => string | null): Middleware {
  return {
    onRequest({ request }) {
      const token = getAccessToken()
      if (!token) return request
      request.headers.set('Authorization', `Bearer ${token}`)
      return request
    },
  }
}
