import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { RoutinesScreen } from '@/screens/RoutinesScreen'
import { findA11yViolations } from '@/test/axe'
import { makeRoutine } from '@/test/fixtures'
import { mockApi, ok } from '@/test/mockApi'

vi.mock('@/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api')>()),
  api: (await import('@/test/mockApi')).mockApi,
}))

const WORKOUT = makeRoutine({ frequency: 'weekly', weekdays: [0, 2], time_limit_minutes: 30 })

beforeEach(() => {
  for (const verb of Object.values(mockApi)) verb.mockReset()
  mockApi.GET.mockImplementation((path: string) => ok(path === '/routines' ? [WORKOUT] : []))
  mockApi.PATCH.mockReturnValue(ok(WORKOUT))
  mockApi.DELETE.mockReturnValue(ok(undefined))
})

describe('RoutinesScreen', () => {
  it('describes each routine without dot-joined text', async () => {
    render(<RoutinesScreen />)

    expect(await screen.findByText(/^Mon, Wed, from /)).toBeInTheDocument()
  })

  it('opens a routine for editing with its schedule', async () => {
    render(<RoutinesScreen />)

    await userEvent.click(await screen.findByRole('button', { name: 'Edit “Workout”' }))

    const dialog = screen.getByRole('dialog', { name: 'Edit routine' })
    expect(within(dialog).getByLabelText('Routine')).toHaveValue('Workout')
    expect(within(dialog).getByLabelText('Repeats')).toHaveValue('weekly')
    expect(within(dialog).getByRole('checkbox', { name: 'Mon' })).toBeChecked()
  })

  it('saves the edited routine', async () => {
    render(<RoutinesScreen />)
    await userEvent.click(await screen.findByRole('button', { name: 'Edit “Workout”' }))
    const dialog = screen.getByRole('dialog', { name: 'Edit routine' })

    await userEvent.click(within(dialog).getByRole('checkbox', { name: 'Fri' }))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save changes' }))

    expect(mockApi.PATCH).toHaveBeenCalledWith('/routines/{routine_id}', {
      params: { path: { routine_id: 'r1' } },
      body: expect.objectContaining({ title: 'Workout', frequency: 'weekly', weekdays: [0, 2, 4] }),
    })
  })

  it('shows and edits the time limit', async () => {
    render(<RoutinesScreen />)
    expect(await screen.findByText(/30 min each time/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Edit “Workout”' }))
    const dialog = screen.getByRole('dialog', { name: 'Edit routine' })
    const amount = within(dialog).getByRole('spinbutton', { name: 'Time limit amount' })
    await userEvent.clear(amount)
    await userEvent.type(amount, '45')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save changes' }))

    expect(mockApi.PATCH.mock.calls[0]?.[1].body.time_limit_minutes).toBe(45)
  })

  it('asks before deleting', async () => {
    render(<RoutinesScreen />)

    await userEvent.click(await screen.findByRole('button', { name: 'Delete “Workout”' }))

    expect(screen.getByRole('dialog', { name: 'Delete this routine?' })).toBeInTheDocument()
    expect(mockApi.DELETE).not.toHaveBeenCalled()
  })

  it('deletes after confirming', async () => {
    render(<RoutinesScreen />)
    await userEvent.click(await screen.findByRole('button', { name: 'Delete “Workout”' }))

    await userEvent.click(screen.getByRole('button', { name: 'Delete routine' }))

    expect(mockApi.DELETE).toHaveBeenCalledWith('/routines/{routine_id}', {
      params: { path: { routine_id: 'r1' } },
    })
  })

  it('has no accessibility violations', async () => {
    const { container } = render(<RoutinesScreen />)
    await screen.findByText(/^Mon, Wed/)

    expect(await findA11yViolations(container)).toEqual([])
  })
})
