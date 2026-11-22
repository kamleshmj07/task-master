import { vi } from 'vitest'

/** `vi.fn()` stand-ins for every API verb, reset between tests. */
export const mockApi = {
  GET: vi.fn(),
  POST: vi.fn(),
  PUT: vi.fn(),
  PATCH: vi.fn(),
  DELETE: vi.fn(),
}

/** Resolve like openapi-fetch does on success. */
export function ok<T>(data: T) {
  return Promise.resolve({ data, error: undefined })
}

/** Resolve like openapi-fetch does on an error response. */
export function fail(error: unknown) {
  return Promise.resolve({ data: undefined, error })
}
