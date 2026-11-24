import type { PlanRead, TaskRead, UserRead } from '@task-master/api-client'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { type Auth, AuthContext } from '@/authContext'
import { addDays, todayIso } from '@/dates'
import { TodayScreen } from '@/screens/TodayScreen'
import { findA11yViolations } from '@/test/axe'
import { makeGoal, makeRoutine, makeTask } from '@/test/fixtures'
import { mockApi, ok } from '@/test/mockApi'

vi.mock('@/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api')>()),
  api: (await import('@/test/mockApi')).mockApi,
}))

const TODAY = todayIso()

const USER: UserRead = {
  id: 'u',
  email: 'ada@example.com',
  timezone: 'UTC',
  display_name: 'Ada',
  is_active: true,
  is_superuser: false,
  is_verified: false,
}

const FOCUS = makeTask({
  id: 'a',
  title: 'Draft proposal',
  due_date: TODAY,
  steps: [
    { id: 's1', text: 'Find the policy', done: true },
    { id: 's2', text: 'Call the broker', done: false },
  ],
  next_step: 'Call the broker',
})
const SECOND = makeTask({ id: 'b', title: 'Run 20 min', due_date: TODAY, next_step: 'Find the policy' })

function plan(overrides: Partial<PlanRead> = {}): PlanRead {
  return {
    plan_date: TODAY,
    top_three: [
      { rank: 1, task: FOCUS },
      { rank: 2, task: SECOND },
    ],
    routines: [{ done: false, streak: 4, routine: makeRoutine() }],
    suggestions: [],
    heads_up: [],
    ...overrides,
  }
}

function mockGets(planData: PlanRead, openTasks: TaskRead[] = []) {
  mockApi.GET.mockImplementation((path: string) => {
    if (path === '/plans/{plan_date}') return ok(planData)
    if (path === '/goals') return ok([makeGoal({ id: 'g1', title: 'Car' })])
    return ok(openTasks)
  })
}

function renderToday() {
  const auth: Auth = {
    user: USER,
    loading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    deleteAccount: vi.fn(),
    setUser: vi.fn(),
  }
  return render(
    <AuthContext.Provider value={auth}>
      <TodayScreen />
    </AuthContext.Provider>,
  )
}

const three = async () => within(await screen.findByRole('region', { name: /Your three/ }))

beforeEach(() => {
  for (const verb of Object.values(mockApi)) verb.mockReset()
  mockApi.PUT.mockReturnValue(ok({}))
  mockApi.PATCH.mockReturnValue(ok(FOCUS))
})

describe('Today header', () => {
  it('greets the user by name', async () => {
    mockGets(plan())
    renderToday()

    expect(await screen.findByRole('heading', { level: 1, name: /, Ada$/ })).toBeInTheDocument()
  })

  it('shows the day at a glance', async () => {
    mockGets(plan({ top_three: [{ rank: 1, task: { ...FOCUS, status: 'done' } }, { rank: 2, task: SECOND }] }))
    renderToday()

    const glance = await screen.findByLabelText('The day so far')
    expect(glance).toHaveTextContent('Your three1 of 2 done')
    expect(glance).toHaveTextContent('Routines0 of 1 done')
  })
})

describe('Your three', () => {
  it('lights only the first open task, with its next step and steps open', async () => {
    mockGets(plan())
    renderToday()

    const list = await three()
    expect(list.getByText('Start here')).toBeInTheDocument()
    expect(list.getAllByText('Start here')).toHaveLength(1)
    expect(list.getByText('Next step')).toBeInTheDocument()
    expect(list.getByRole('checkbox', { name: 'Call the broker' })).toBeInTheDocument()
  })

  it('keeps the other tasks quiet until their steps are opened', async () => {
    mockGets(plan())
    renderToday()

    const list = await three()
    expect(list.getByText('Next: Find the policy')).toBeInTheDocument()
    await userEvent.click(list.getByRole('button', { name: /Show steps for “Run 20 min”/ }))

    expect(list.getByRole('button', { name: /Hide steps for “Run 20 min”/ })).toHaveAttribute('aria-expanded', 'true')
  })

  it('ticks a step without leaving Today', async () => {
    mockGets(plan())
    renderToday()

    await userEvent.click((await three()).getByRole('checkbox', { name: 'Call the broker' }))

    expect(mockApi.PATCH).toHaveBeenCalledWith('/tasks/{task_id}/steps/{step_id}', {
      params: { path: { task_id: 'a', step_id: 's2' } },
      body: { done: true },
    })
  })

  it('asks to complete the task once every step is ticked', async () => {
    mockGets(plan())
    mockApi.PATCH.mockReturnValue(ok({ ...FOCUS, steps: FOCUS.steps.map((s) => ({ ...s, done: true })), next_step: null }))
    renderToday()

    await userEvent.click((await three()).getByRole('checkbox', { name: 'Call the broker' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Mark complete' }))

    expect(mockApi.PATCH).toHaveBeenLastCalledWith('/tasks/{task_id}', {
      params: { path: { task_id: 'a' } },
      body: { status: 'done' },
    })
  })

  it('moves the lamp on once the first task is done', async () => {
    mockGets(plan({ top_three: [{ rank: 1, task: { ...FOCUS, status: 'done', completed_at: `${TODAY}T09:40:00` } }, { rank: 2, task: SECOND }] }))
    renderToday()

    const list = await three()
    const lit = list.getByText('Start here').closest('li')
    expect(lit).toHaveTextContent('Run 20 min')
    expect(list.getByText(/^Done at /)).toBeInTheDocument()
  })

  it('reorders and removes tasks after Change', async () => {
    mockGets(plan())
    renderToday()
    const list = await three()

    await userEvent.click(list.getByRole('button', { name: 'Change' }))
    await userEvent.click(list.getByRole('button', { name: 'Move “Run 20 min” up' }))

    expect(mockApi.PUT).toHaveBeenCalledWith('/plans/{plan_date}', {
      params: { path: { plan_date: TODAY } },
      body: { task_ids: ['b', 'a'] },
    })
  })

  it('shows the free slots', async () => {
    mockGets(plan())
    renderToday()

    expect((await three()).getByText('If there is time: pick a task below')).toBeInTheDocument()
  })
})

describe('Suggestions', () => {
  const suggestions: PlanRead['suggestions'] = [
    { kind: 'left_over', task: makeTask({ id: 'l', title: 'Sort receipts' }), previous_rank: 2, goal_title: null },
    { kind: 'overdue', task: makeTask({ id: 'o', title: 'Renew passport', due_date: addDays(TODAY, -3) }), previous_rank: null, goal_title: null },
    { kind: 'goal_next', task: makeTask({ id: 'g', title: 'Buy shoes' }), previous_rank: null, goal_title: 'Run a marathon' },
  ]

  it('asks what would make a good day when nothing is picked', async () => {
    mockGets(plan({ top_three: [], suggestions }))
    renderToday()

    expect(await screen.findByRole('heading', { name: 'What would make today a good day?' })).toBeInTheDocument()
  })

  it('puts yesterday first, then the rest, each with why', async () => {
    mockGets(plan({ top_three: [], suggestions }))
    renderToday()

    expect(await screen.findByRole('heading', { name: 'Left from yesterday' })).toBeInTheDocument()
    expect(screen.getByText(/^Was number 2 yesterday/)).toBeInTheDocument()
    expect(screen.getByText('Overdue by 3 days')).toBeInTheDocument()
    expect(screen.getByText('Next for Run a marathon')).toBeInTheDocument()
  })

  it('adds a suggestion to the next free slot', async () => {
    mockGets(plan({ suggestions }))
    renderToday()

    await userEvent.click(await screen.findByRole('button', { name: 'Add “Renew passport” to your three' }))

    expect(mockApi.PUT).toHaveBeenCalledWith('/plans/{plan_date}', {
      params: { path: { plan_date: TODAY } },
      body: { task_ids: ['a', 'b', 'o'] },
    })
  })

  it('can choose any other open task', async () => {
    mockGets(plan({ suggestions: [] }), [makeTask({ id: 'x', title: 'Fix the bike' })])
    renderToday()

    await userEvent.click(await screen.findByRole('button', { name: 'Choose another task' }))
    await userEvent.selectOptions(await screen.findByLabelText('Choose a task'), 'x')

    expect(mockApi.PUT).toHaveBeenCalledWith('/plans/{plan_date}', {
      params: { path: { plan_date: TODAY } },
      body: { task_ids: ['a', 'b', 'x'] },
    })
  })

  it('is hidden once three are picked', async () => {
    mockGets(plan({ top_three: [1, 2, 3].map((rank) => ({ rank, task: makeTask({ id: `t${rank}`, title: `T${rank}` }) })) }))
    renderToday()

    await three()
    expect(screen.queryByRole('button', { name: 'Choose another task' })).not.toBeInTheDocument()
  })
})

describe('Routines and heads-up', () => {
  it('ticks a routine off and shows its streak', async () => {
    mockGets(plan())
    renderToday()

    expect(await screen.findByText('4-day streak')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('checkbox', { name: /Workout/ }))

    expect(mockApi.PUT).toHaveBeenCalledWith('/routines/{routine_id}/completions/{day}', {
      params: { path: { routine_id: 'r1', day: TODAY } },
    })
  })

  it('lists what needs a decision, with one action each', async () => {
    mockGets(
      plan({
        heads_up: [
          { kind: 'overdue', task: makeTask({ id: 'o', title: 'Renew passport', due_date: addDays(TODAY, -3) }) },
          { kind: 'ready', task: makeTask({ id: 'r', title: 'Call the plumber' }) },
        ],
      }),
    )
    renderToday()
    const headsUp = within(await screen.findByRole('region', { name: 'Heads-up' }))

    await userEvent.click(headsUp.getByRole('button', { name: 'Complete “Call the plumber”' }))

    expect(headsUp.getByRole('button', { name: 'Postpone “Renew passport”' })).toBeInTheDocument()
    expect(mockApi.PATCH).toHaveBeenCalledWith('/tasks/{task_id}', {
      params: { path: { task_id: 'r' } },
      body: { status: 'done' },
    })
  })

  it('says when nothing needs you', async () => {
    mockGets(plan())
    renderToday()

    expect(await screen.findByText('Nothing needs you today.')).toBeInTheDocument()
  })
})

describe('Other days', () => {
  it('shows a past day read-only', async () => {
    mockGets(plan())
    renderToday()
    await three()

    await userEvent.click(screen.getByRole('button', { name: 'Previous day' }))

    expect(await screen.findByText('A past day')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Change' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Heads-up' })).not.toBeInTheDocument()
  })
})

it('has no accessibility violations', async () => {
  mockGets(plan({ suggestions: [{ kind: 'overdue', task: makeTask({ id: 'o', title: 'Renew passport' }), previous_rank: null, goal_title: null }] }))
  const { container } = renderToday()
  await three()

  expect(await findA11yViolations(container)).toEqual([])
})
