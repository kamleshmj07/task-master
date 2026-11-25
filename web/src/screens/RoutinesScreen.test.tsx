import type { DayMark, DueRoutine } from '@task-master/api-client'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { todayIso } from '@/dates'
import { RoutinesScreen } from '@/screens/RoutinesScreen'
import { findA11yViolations } from '@/test/axe'
import { makeDueRoutine, makeRoutine } from '@/test/fixtures'
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
  it('invites the first routine when there are none', async () => {
    mockApi.GET.mockReturnValue(ok([]))
    render(<RoutinesScreen />)

    await userEvent.click(await screen.findByRole('button', { name: 'New routine' }))

    expect(screen.getByLabelText('Routine')).toHaveFocus()
  })

  it('has no goal field', async () => {
    render(<RoutinesScreen />)

    expect(await screen.findByRole('form', { name: 'New routine' })).not.toHaveTextContent('Goal')
  })

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

describe('RoutinesScreen due today', () => {
  const WATER = makeRoutine({ id: 'r2', title: 'Water the plants' })

  function mockDue(due: DueRoutine[]) {
    mockApi.GET.mockImplementation((path: string) =>
      ok(path === '/routines/due' ? due : path === '/routines' ? [WORKOUT, WATER] : []),
    )
  }

  it('lists only the routines due today, with how many are done', async () => {
    mockDue([makeDueRoutine({ routine: WATER, done: true, streak: 12 })])
    render(<RoutinesScreen />)

    const section = await screen.findByRole('region', { name: /Due today/ })

    expect(within(section).getByText('Water the plants')).toBeInTheDocument()
    expect(section).toHaveTextContent('1 of 1 done')
    expect(section).toHaveTextContent('12 days in a row')
  })

  it('reads the last seven days aloud', async () => {
    const recentDays: DayMark[] = ['done', 'missed', 'not_due', 'done', 'done', 'not_due', 'open']
    mockDue([makeDueRoutine({ routine: WATER, recent_days: recentDays })])
    render(<RoutinesScreen />)

    expect(await screen.findByRole('img', { name: 'Last 7 days: done 3 of 5 days it was due' })).toBeInTheDocument()
  })

  it('ticks a routine off for today', async () => {
    mockDue([makeDueRoutine({ routine: WATER })])
    mockApi.PUT.mockReturnValue(ok(undefined))
    render(<RoutinesScreen />)

    await userEvent.click(await screen.findByRole('button', { name: 'Done today: Water the plants' }))

    expect(mockApi.PUT).toHaveBeenCalledWith('/routines/{routine_id}/completions/{day}', {
      params: { path: { routine_id: 'r2', day: todayIso() } },
    })
  })

  it('unticks a routine already done today', async () => {
    mockDue([makeDueRoutine({ routine: WATER, done: true })])
    render(<RoutinesScreen />)

    const tick = await screen.findByRole('button', { name: 'Done today: Water the plants' })
    expect(tick).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(tick)

    expect(mockApi.DELETE).toHaveBeenCalledWith('/routines/{routine_id}/completions/{day}', {
      params: { path: { routine_id: 'r2', day: todayIso() } },
    })
  })

  it('hides the section when nothing is due', async () => {
    render(<RoutinesScreen />)
    await screen.findByText(/^Mon, Wed/)

    expect(screen.queryByRole('region', { name: /Due today/ })).not.toBeInTheDocument()
  })

  it('has no accessibility violations with routines due', async () => {
    mockDue([makeDueRoutine({ routine: WATER, done: true, streak: 3 })])
    const { container } = render(<RoutinesScreen />)
    await screen.findByRole('region', { name: /Due today/ })

    expect(await findA11yViolations(container)).toEqual([])
  })
})
