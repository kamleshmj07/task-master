import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from '@/App'
import { findA11yViolations } from '@/test/axe'
import { mockApi, ok } from '@/test/mockApi'

const { refreshSession } = vi.hoisted(() => ({
  refreshSession: vi.fn<() => Promise<boolean>>(),
}))

vi.mock('@/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api')>()),
  api: (await import('@/test/mockApi')).mockApi,
  refreshSession: () => refreshSession(),
}))

beforeEach(() => {
  refreshSession.mockReset()
})

describe('App', () => {
  it('asks a signed-out visitor to sign in', async () => {
    refreshSession.mockResolvedValue(false)
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('switches to account creation', async () => {
    refreshSession.mockResolvedValue(false)
    render(<App />)

    await userEvent.click(await screen.findByRole('button', { name: /Create an account/ }))

    expect(screen.getByRole('heading', { name: 'Create account' })).toBeInTheDocument()
  })

  it('offers Settings and Sign out from the account menu', async () => {
    refreshSession.mockResolvedValue(true)
    mockApi.GET.mockImplementation((path: string) => {
      if (path === '/users/me') {
        return ok({
          id: 'u',
          email: 'ada@example.com',
          timezone: 'UTC',
          is_active: true,
          is_superuser: false,
          is_verified: false,
        })
      }
      if (path === '/plans/{plan_date}') {
        return ok({ plan_date: '2026-11-22', top_three: [], routines: [] })
      }
      return ok([])
    })
    mockApi.POST.mockReturnValue(ok(undefined))
    render(<App />)

    await userEvent.click(await screen.findByRole('button', { name: /ada@example.com/ }))
    expect(screen.getByRole('menuitem', { name: 'Settings' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('menuitem', { name: 'Sign out' }))

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('has no accessibility violations on the sign-in page', async () => {
    refreshSession.mockResolvedValue(false)
    const { container } = render(<App />)
    await screen.findByRole('heading', { name: 'Sign in' })

    expect(await findA11yViolations(container)).toEqual([])
  })
})
