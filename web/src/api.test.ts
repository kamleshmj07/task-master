import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { errorMessage, fetchWithRefresh, setAccessToken } from '@/api'

const fetchMock = vi.fn<typeof fetch>()

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
  setAccessToken('old-token')
})

afterEach(() => {
  vi.unstubAllGlobals()
  fetchMock.mockReset()
})

function status(code: number, body: unknown = {}) {
  return Response.json(body, { status: code })
}

describe('fetchWithRefresh', () => {
  it('passes successful responses straight through', async () => {
    fetchMock.mockResolvedValueOnce(status(200))

    const response = await fetchWithRefresh(new Request('http://api.test/tasks'))

    expect([response.status, fetchMock.mock.calls.length]).toEqual([200, 1])
  })

  it('refreshes once and retries with the new token after a 401', async () => {
    fetchMock
      .mockResolvedValueOnce(status(401))
      .mockResolvedValueOnce(status(200, { access_token: 'new-token' }))
      .mockResolvedValueOnce(status(200))

    const response = await fetchWithRefresh(new Request('http://api.test/tasks'))

    const retried = fetchMock.mock.calls[2]?.[0] as Request
    expect(response.status).toBe(200)
    expect(retried.headers.get('Authorization')).toBe('Bearer new-token')
  })

  it('returns the 401 when the refresh fails', async () => {
    fetchMock.mockResolvedValueOnce(status(401)).mockResolvedValueOnce(status(401))

    const response = await fetchWithRefresh(new Request('http://api.test/tasks'))

    expect([response.status, fetchMock.mock.calls.length]).toEqual([401, 2])
  })

  it('never refreshes for auth calls', async () => {
    fetchMock.mockResolvedValueOnce(status(401))

    await fetchWithRefresh(new Request('http://api.test/auth/web/logout'))

    expect(fetchMock.mock.calls.length).toBe(1)
  })
})

describe('errorMessage', () => {
  it('translates known error codes', () => {
    expect(errorMessage({ detail: 'LOGIN_BAD_CREDENTIALS' })).toBe(
      'Wrong email or password.',
    )
  })

  it('uses the first validation message without its prefix', () => {
    expect(
      errorMessage({ detail: [{ msg: "Value error, A note is required when the reason is 'other'" }] }),
    ).toBe("A note is required when the reason is 'other'")
  })

  it('falls back to a generic message', () => {
    expect(errorMessage(undefined)).toBe('Something went wrong. Please try again.')
  })
})
