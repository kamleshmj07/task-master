import type { PlanRead, TaskRead } from '@task-master/api-client'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { TodayScreen } from '@/screens/TodayScreen'
import { findA11yViolations } from '@/test/axe'
import { makeRoutine, makeTask } from '@/test/fixtures'
import { mockApi, ok } from '@/test/mockApi'

vi.mock('@/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api')>()),
  api: (await import('@/test/mockApi')).mockApi,
}))

function plan(overrides: Partial<PlanRead> = {}): PlanRead {
  return {
    plan_date: '2026-11-22',
    top_three: [{ rank: 1, task: makeTask({ id: 'a', title: 'Draft proposal' }) }],
    routines: [{ done: false, streak: 4, routine: makeRoutine() }],
    ...overrides,
  }
}

function mockGets(planData: PlanRead, openTasks: TaskRead[] = []) {
  mockApi.GET.mockImplementation((path: string) =>
    ok(path === '/plans/{plan_date}' ? planData : openTasks),
  )
}

beforeEach(() => {
  for (const verb of Object.values(mockApi)) verb.mockReset()
  mockApi.PUT.mockReturnValue(ok({}))
})

describe('TodayScreen', () => {
  it('lists the Top 3 and routines in separate sections', async () => {
    mockGets(plan())
    render(<TodayScreen />)

    const topThree = (await screen.findByRole('heading', { name: 'Top 3' })).parentElement
    const routines = screen.getByRole('heading', { name: 'Routines' }).parentElement
    expect(within(topThree!).getByText('Draft proposal')).toBeInTheDocument()
    expect(within(routines!).getByText('Workout')).toBeInTheDocument()
  })

  it("shows each Top 3 task's next step", async () => {
    mockGets(plan())
    render(<TodayScreen />)

    expect(await screen.findByText('Next: Find the policy')).toBeInTheDocument()
  })

  it('shows the routine streak', async () => {
    mockGets(plan())
    render(<TodayScreen />)

    expect(await screen.findByText('4-day streak')).toBeInTheDocument()
  })

  it('no longer shows a capacity meter', async () => {
    mockGets(plan())
    render(<TodayScreen />)
    await screen.findByText('Draft proposal')

    expect(screen.queryByRole('meter')).not.toBeInTheDocument()
  })

  it('ticks a routine off', async () => {
    mockGets(plan())
    render(<TodayScreen />)

    await userEvent.click(await screen.findByRole('checkbox', { name: 'Tick "Workout"' }))

    expect(mockApi.PUT).toHaveBeenCalledWith('/routines/{routine_id}/completions/{day}', {
      params: { path: { routine_id: 'r1', day: expect.any(String) } },
    })
  })

  it('adds a task to the Top 3', async () => {
    mockGets(plan(), [
      makeTask({ id: 'a', title: 'Draft proposal' }),
      makeTask({ id: 'b', title: 'Call the bank' }),
    ])
    render(<TodayScreen />)

    await userEvent.selectOptions(
      await screen.findByRole('combobox', { name: 'Add a task' }),
      'Call the bank (Someday)',
    )

    expect(mockApi.PUT.mock.calls[0]?.[1].body).toEqual({ task_ids: ['a', 'b'] })
  })

  it('has no accessibility violations', async () => {
    mockGets(plan())
    const { container } = render(<TodayScreen />)
    await screen.findByText('Draft proposal')

    expect(await findA11yViolations(container)).toEqual([])
  })
})
