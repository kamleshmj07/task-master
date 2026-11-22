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

  function signedInAs(displayName: string | null) {
    refreshSession.mockResolvedValue(true)
    mockApi.GET.mockImplementation((path: string) => {
      if (path === '/users/me') {
        return ok({
          id: 'u',
          email: 'ada@example.com',
          timezone: 'Asia/Kolkata',
          display_name: displayName,
          is_active: true,
          is_superuser: false,
          is_verified: false,
        })
      }
      if (path === '/plans/{plan_date}') {
        return ok({ plan_date: '2026-11-22', top_three: [], routines: [] })
      }
      if (path === '/notifications/unread-count') return ok({ unread: 0 })
      return ok([])
    })
    mockApi.POST.mockReturnValue(ok(undefined))
  }

  it('asks a new user for their name first', async () => {
    signedInAs(null)
    render(<App />)

    expect(await screen.findByRole('dialog', { name: 'Welcome to Task Master' })).toBeInTheDocument()
  })

  it('saves the name and timezone from the welcome dialog', async () => {
    signedInAs(null)
    mockApi.PATCH.mockReturnValue(
      ok({
        id: 'u',
        email: 'ada@example.com',
        timezone: 'Asia/Kolkata',
        display_name: 'Ada',
        is_active: true,
        is_superuser: false,
        is_verified: false,
      }),
    )
    render(<App />)

    await userEvent.type(await screen.findByRole('textbox', { name: 'Your name' }), 'Ada')
    await userEvent.click(screen.getByRole('button', { name: 'Get started' }))

    expect(mockApi.PATCH).toHaveBeenCalledWith('/users/me', {
      body: { display_name: 'Ada', timezone: 'Asia/Kolkata' },
    })
    expect(screen.queryByRole('dialog', { name: 'Welcome to Task Master' })).not.toBeInTheDocument()
  })

  it('skips the welcome dialog once a name is set', async () => {
    signedInAs('Ada Lovelace')
    render(<App />)

    expect(await screen.findByRole('button', { name: /Ada Lovelace/ })).toBeInTheDocument()
    expect(screen.queryByRole('dialog', { name: 'Welcome to Task Master' })).not.toBeInTheDocument()
  })

  it('offers Settings and Sign out from the account menu', async () => {
    signedInAs('Ada Lovelace')
    render(<App />)

    await userEvent.click(await screen.findByRole('button', { name: /Ada Lovelace/ }))
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
