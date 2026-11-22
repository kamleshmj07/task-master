import { describe, expect, it, vi } from 'vitest'

import { createApiClient } from './index'

function fakeFetch() {
  return vi.fn(async (_request: Request) =>
    Response.json({ status: 'ok' }, { status: 200 }),
  )
}

function sentRequest(fetch: ReturnType<typeof fakeFetch>): Request {
  const request = fetch.mock.calls[0]?.[0]
  if (!request) throw new Error('fetch was not called')
  return request
}

describe('createApiClient', () => {
  it('sends the access token as a bearer header', async () => {
    const fetch = fakeFetch()
    const client = createApiClient({
      baseUrl: 'https://api.test',
      getAccessToken: () => 'abc',
      fetch,
    })

    await client.GET('/users/me')

    expect(sentRequest(fetch).headers.get('Authorization')).toBe('Bearer abc')
  })

  it('omits the header when logged out', async () => {
    const fetch = fakeFetch()
    const client = createApiClient({
      baseUrl: 'https://api.test',
      getAccessToken: () => null,
      fetch,
    })

    await client.GET('/health')

    expect(sentRequest(fetch).headers.has('Authorization')).toBe(false)
  })

  it('targets the configured base URL', async () => {
    const fetch = fakeFetch()
    const client = createApiClient({
      baseUrl: 'https://api.test',
      getAccessToken: () => null,
      fetch,
    })

    await client.GET('/health')

    expect(sentRequest(fetch).url).toBe('https://api.test/health')
  })
})
