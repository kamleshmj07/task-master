import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from '@/App'
import { findA11yViolations } from '@/test/axe'

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

  it('has no accessibility violations on the sign-in page', async () => {
    refreshSession.mockResolvedValue(false)
    const { container } = render(<App />)
    await screen.findByRole('heading', { name: 'Sign in' })

    expect(await findA11yViolations(container)).toEqual([])
  })
})
