import type { GoalRead, TaskRead } from '@task-master/api-client'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { todayIso } from '@/dates'
import { TasksScreen } from '@/screens/TasksScreen'
import { findA11yViolations } from '@/test/axe'
import { makeTask } from '@/test/fixtures'
import { mockApi, ok } from '@/test/mockApi'

vi.mock('@/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api')>()),
  api: (await import('@/test/mockApi')).mockApi,
}))

const GOALS: GoalRead[] = [
  {
    id: 'g1',
    title: 'Essentials',
    why: null,
    deadline: null,
    status: 'active',
    created_at: '',
    updated_at: '',
  },
]

const TODAY = todayIso()

function mockData(tasks: TaskRead[]) {
  mockApi.GET.mockImplementation((path: string, options?: { params?: { query?: { status?: string } } }) => {
    if (path === '/goals') return ok(GOALS)
    const status = options?.params?.query?.status
    return ok(tasks.filter((task) => task.status === status))
  })
}

beforeEach(() => {
  for (const verb of Object.values(mockApi)) verb.mockReset()
})

describe('TasksScreen views', () => {
  it('counts tasks in each view', async () => {
    mockData([
      makeTask({ id: 'a', due_date: TODAY }),
      makeTask({ id: 'b', due_date: null }),
      makeTask({ id: 'c', due_date: null }),
      makeTask({ id: 'd', status: 'done' }),
    ])
    render(<TasksScreen />)

    expect(await screen.findByRole('tab', { name: 'Scheduled 1' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(screen.getByRole('tab', { name: 'Someday 2' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Done 1' })).toBeInTheDocument()
  })

  it('groups scheduled tasks by when they are due', async () => {
    mockData([
      makeTask({ id: 'a', title: 'Due today', due_date: TODAY }),
      makeTask({ id: 'b', title: 'Due later', due_date: '2099-01-01' }),
    ])
    render(<TasksScreen />)

    const today = await screen.findByRole('region', { name: 'Today' })
    expect(within(today).getByText('Due today')).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Later' })).getByText('Due later')).toBeInTheDocument()
  })

  it('switches to Someday', async () => {
    mockData([makeTask({ title: 'Undated', due_date: null })])
    render(<TasksScreen />)

    await userEvent.click(await screen.findByRole('tab', { name: /Someday/ }))

    expect(screen.getByText('Undated')).toBeInTheDocument()
  })

  it('filters by goal', async () => {
    mockData([
      makeTask({ id: 'a', title: 'With goal', goal_id: 'g1', due_date: TODAY }),
      makeTask({ id: 'b', title: 'Without goal', due_date: TODAY }),
    ])
    render(<TasksScreen />)

    await userEvent.click(await screen.findByRole('button', { name: 'No goal', pressed: false }))

    expect(screen.queryByText('With goal')).not.toBeInTheDocument()
    expect(screen.getByText('Without goal')).toBeInTheDocument()
  })

  it('shows the next step on each card', async () => {
    mockData([makeTask({ due_date: TODAY })])
    render(<TasksScreen />)

    expect(await screen.findByText('Find the policy')).toBeInTheDocument()
  })

  it('has no accessibility violations', async () => {
    mockData([makeTask({ due_date: TODAY, postpone_count: 2, time_limit_minutes: 45 })])
    const { container } = render(<TasksScreen />)
    await screen.findByText('Renew insurance')

    expect(await findA11yViolations(container)).toEqual([])
  })
})

describe('TasksScreen steps', () => {
  it('asks before completing a task whose last step is ticked', async () => {
    const task = makeTask({
      due_date: TODAY,
      steps: [
        { id: 's1', text: 'Find the policy', done: true },
        { id: 's2', text: 'Call the broker', done: false },
      ],
    })
    mockData([task])
    mockApi.PATCH.mockReturnValue(
      ok(makeTask({ ...task, steps: task.steps.map((s) => ({ ...s, done: true })) })),
    )
    render(<TasksScreen />)

    await userEvent.click(await screen.findByRole('button', { name: /Show steps/ }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'Call the broker' }))

    expect(await screen.findByRole('dialog', { name: 'All steps done' })).toBeInTheDocument()
  })

  it('completes the task only after confirming', async () => {
    const task = makeTask({ due_date: TODAY, steps: [{ id: 's1', text: 'Only', done: false }] })
    mockData([task])
    mockApi.PATCH.mockReturnValue(ok(makeTask({ ...task, steps: [{ id: 's1', text: 'Only', done: true }] })))
    render(<TasksScreen />)
    await userEvent.click(await screen.findByRole('button', { name: /Show steps/ }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'Only' }))

    await userEvent.click(await screen.findByRole('button', { name: 'Mark complete' }))

    expect(mockApi.PATCH).toHaveBeenLastCalledWith('/tasks/{task_id}', {
      params: { path: { task_id: 't1' } },
      body: { status: 'done' },
    })
  })

  it('keeps the task open on "Not yet"', async () => {
    const task = makeTask({ due_date: TODAY, steps: [{ id: 's1', text: 'Only', done: false }] })
    mockData([task])
    mockApi.PATCH.mockReturnValue(ok(makeTask({ ...task, steps: [{ id: 's1', text: 'Only', done: true }] })))
    render(<TasksScreen />)
    await userEvent.click(await screen.findByRole('button', { name: /Show steps/ }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'Only' }))

    await userEvent.click(await screen.findByRole('button', { name: 'Not yet' }))

    expect(mockApi.PATCH).toHaveBeenCalledTimes(1)
  })

  it('adds a step', async () => {
    mockData([makeTask({ due_date: TODAY })])
    mockApi.POST.mockReturnValue(ok(makeTask()))
    render(<TasksScreen />)
    await userEvent.click(await screen.findByRole('button', { name: /Show steps/ }))

    await userEvent.type(screen.getByRole('textbox', { name: /Add a step/ }), 'Pay{Enter}')

    expect(mockApi.POST).toHaveBeenCalledWith('/tasks/{task_id}/steps', {
      params: { path: { task_id: 't1' } },
      body: { text: 'Pay' },
    })
  })
})

describe('New task', () => {
  it('creates a task with its steps, goal and time limit', async () => {
    mockData([])
    mockApi.POST.mockReturnValue(ok(makeTask()))
    render(<TasksScreen />)

    await userEvent.click(await screen.findByRole('button', { name: '+ New task' }))
    const form = screen.getByRole('form', { name: 'New task' })
    await userEvent.type(within(form).getByRole('textbox', { name: 'Task' }), 'Renew insurance')
    await userEvent.type(within(form).getByRole('textbox', { name: 'Step 1' }), 'Find the policy')
    await userEvent.click(within(form).getByRole('button', { name: '+ Add step' }))
    await userEvent.type(within(form).getByRole('textbox', { name: 'Step 2' }), 'Call the broker')
    await userEvent.selectOptions(within(form).getByRole('combobox', { name: 'Goal' }), 'Essentials')
    await userEvent.selectOptions(within(form).getByRole('combobox', { name: /Time limit/ }), '45 min')
    await userEvent.click(within(form).getByRole('button', { name: 'Add task' }))

    expect(mockApi.POST).toHaveBeenCalledWith('/tasks', {
      body: {
        title: 'Renew insurance',
        steps: ['Find the policy', 'Call the broker'],
        goal_id: 'g1',
        time_limit_minutes: 45,
        due_date: null,
      },
    })
  })

  it('creates a new goal inline', async () => {
    mockData([])
    mockApi.POST.mockReturnValue(ok({ ...GOALS[0], id: 'g2', title: 'Fitness' }))
    render(<TasksScreen />)

    await userEvent.click(await screen.findByRole('button', { name: '+ New task' }))
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Goal' }), '+ New goal…')
    await userEvent.type(screen.getByRole('textbox', { name: 'New goal name' }), 'Fitness')
    await userEvent.click(screen.getByRole('button', { name: 'Create' }))

    expect(mockApi.POST).toHaveBeenCalledWith('/goals', { body: { title: 'Fitness' } })
  })

  it('requires a first step', async () => {
    mockData([])
    render(<TasksScreen />)

    await userEvent.click(await screen.findByRole('button', { name: '+ New task' }))

    expect(screen.getByRole('textbox', { name: 'Step 1' })).toBeRequired()
  })
})

describe('Postponing', () => {
  it('opens the postpone pop-up', async () => {
    mockData([makeTask({ due_date: TODAY })])
    render(<TasksScreen />)

    await userEvent.click(await screen.findByRole('button', { name: 'Postpone' }))

    expect(screen.getByRole('dialog', { name: 'Why are you putting this off?' })).toBeInTheDocument()
  })
})
