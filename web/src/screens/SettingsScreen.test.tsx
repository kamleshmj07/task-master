import type { UserRead } from '@task-master/api-client'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { type Auth, AuthContext } from '@/authContext'
import { SettingsScreen } from '@/screens/SettingsScreen'
import { findA11yViolations } from '@/test/axe'
import { mockApi, ok } from '@/test/mockApi'

vi.mock('@/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api')>()),
  api: (await import('@/test/mockApi')).mockApi,
}))

const USER: UserRead = {
  id: 'u',
  email: 'ada@example.com',
  timezone: 'Asia/Kolkata',
  display_name: 'Ada',
  is_active: true,
  is_superuser: false,
  is_verified: false,
}

function renderSettings(overrides: Partial<Auth> = {}) {
  const auth: Auth = {
    user: USER,
    loading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    deleteAccount: vi.fn().mockResolvedValue(null),
    setUser: vi.fn(),
    ...overrides,
  }
  const view = render(
    <AuthContext.Provider value={auth}>
      <SettingsScreen />
    </AuthContext.Provider>,
  )
  return { auth, ...view }
}

beforeEach(() => {
  mockApi.PATCH.mockReset()
})

describe('SettingsScreen profile', () => {
  it('shows the current details', () => {
    renderSettings()

    expect(screen.getByRole('textbox', { name: 'Your name' })).toHaveValue('Ada')
    expect(screen.getByRole('combobox', { name: /Timezone/ })).toHaveValue('Asia/Kolkata')
    expect(screen.getByRole('textbox', { name: 'Email' })).toHaveAttribute('readonly')
  })

  it('saves name and timezone', async () => {
    mockApi.PATCH.mockReturnValue(ok({ ...USER, display_name: 'Ada L' }))
    const { auth } = renderSettings()

    await userEvent.clear(screen.getByRole('textbox', { name: 'Your name' }))
    await userEvent.type(screen.getByRole('textbox', { name: 'Your name' }), 'Ada L')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect(mockApi.PATCH).toHaveBeenCalledWith('/users/me', {
      body: { display_name: 'Ada L', timezone: 'Asia/Kolkata' },
    })
    expect(auth.setUser).toHaveBeenCalled()
  })

  it('has no accessibility violations', async () => {
    const { container } = renderSettings()

    expect(await findA11yViolations(container)).toEqual([])
  })
})

describe('SettingsScreen delete account', () => {
  it('asks for the password before deleting', async () => {
    const { auth } = renderSettings()

    await userEvent.click(screen.getByRole('button', { name: 'Delete account…' }))
    await userEvent.type(screen.getByLabelText('Password'), 'correct-horse-battery')
    await userEvent.click(screen.getByRole('button', { name: 'Delete everything' }))

    expect(auth.deleteAccount).toHaveBeenCalledWith('correct-horse-battery')
  })

  it('shows the error when the password is wrong', async () => {
    renderSettings({ deleteAccount: vi.fn().mockResolvedValue('Password is incorrect') })

    await userEvent.click(screen.getByRole('button', { name: 'Delete account…' }))
    await userEvent.type(screen.getByLabelText('Password'), 'nope')
    await userEvent.click(screen.getByRole('button', { name: 'Delete everything' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Password is incorrect')
  })

  it('can be cancelled', async () => {
    const { auth } = renderSettings()

    await userEvent.click(screen.getByRole('button', { name: 'Delete account…' }))
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(auth.deleteAccount).not.toHaveBeenCalled()
  })
})
