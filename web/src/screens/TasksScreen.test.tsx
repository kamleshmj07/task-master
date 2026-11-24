import type { GoalRead, TaskRead } from '@task-master/api-client'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { todayIso } from '@/dates'
import { TasksScreen } from '@/screens/TasksScreen'
import { findA11yViolations } from '@/test/axe'
import { makeGoal, makeTask } from '@/test/fixtures'
import { mockApi, ok } from '@/test/mockApi'

vi.mock('@/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api')>()),
  api: (await import('@/test/mockApi')).mockApi,
}))

const GOALS: GoalRead[] = [makeGoal()]

const HISTORY = [
  { id: 'p1', task_id: 't1', from_date: '2099-01-01', to_date: '2099-01-05', reason: 'blocked', note: 'Waiting on Sam', created_at: '2026-11-10T10:00:00Z' },
  { id: 'p2', task_id: 't1', from_date: '2099-01-05', to_date: null, reason: 'blocked', note: null, created_at: '2026-11-20T10:00:00Z' },
]

const TODAY = todayIso()

type View = 'scheduled' | 'review' | 'someday' | 'done'

interface Query {
  view?: View
  goal_id?: string
  no_goal?: boolean
  limit?: number
  offset?: number
}

/** The API's rule: each task sits in exactly one view. */
function viewOf(task: TaskRead): View {
  if (task.status === 'done') return 'done'
  const overdue = task.due_date !== null && task.due_date < TODAY
  if (task.next_step === null || overdue) return 'review'
  return task.due_date === null ? 'someday' : 'scheduled'
}

/** Answer `/goals`, `/tasks` and `/tasks/counts` the way the API does. */
function mockData(tasks: TaskRead[]) {
  mockApi.GET.mockImplementation((path: string, options?: { params?: { query?: Query } }) => {
    if (path === '/goals') return ok(GOALS)
    if (path === '/tasks/{task_id}/postponements') return ok(HISTORY)
    const query = options?.params?.query ?? {}
    const byGoal = tasks.filter((task) =>
      query.no_goal ? task.goal_id === null : !query.goal_id || task.goal_id === query.goal_id,
    )
    const count = (view: View) => byGoal.filter((task) => viewOf(task) === view).length
    if (path === '/tasks/counts') {
      return ok({
        scheduled: count('scheduled'),
        review: count('review'),
        someday: count('someday'),
        done: count('done'),
      })
    }
    const matching = byGoal.filter((task) => viewOf(task) === query.view)
    const offset = query.offset ?? 0
    return ok(matching.slice(offset, offset + (query.limit ?? 50)))
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
      makeTask({ id: 'a', title: 'Morning task', due_date: TODAY }),
      makeTask({ id: 'b', title: 'Distant task', due_date: '2099-01-01' }),
    ])
    render(<TasksScreen />)

    const today = await screen.findByRole('region', { name: 'Today' })
    expect(within(today).getByText('Morning task')).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Later' })).getByText('Distant task')).toBeInTheDocument()
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

  it('shows the next step on each card, apart from the title', async () => {
    mockData([makeTask({ due_date: TODAY })])
    render(<TasksScreen />)

    expect(await screen.findByText('Next step')).toBeInTheDocument()
    expect(screen.getByText('Find the policy')).toHaveClass('next-text')
  })

  it('has no accessibility violations', async () => {
    mockData([makeTask({ due_date: TODAY, postpone_count: 2, time_limit_minutes: 45 })])
    const { container } = render(<TasksScreen />)
    await screen.findByText('Renew insurance')

    expect(await findA11yViolations(container)).toEqual([])
  })
})

describe('TasksScreen review', () => {
  it('moves overdue tasks and finished-step tasks to Review', async () => {
    mockData([
      makeTask({ id: 'late', title: 'Late one', due_date: '2020-01-01' }),
      makeTask({ id: 'ready', title: 'Ready one', steps: [{ id: 's', text: 'Only', done: true }] }),
      makeTask({ id: 'soon', title: 'Soon one', due_date: '2099-01-01' }),
    ])
    render(<TasksScreen />)

    await userEvent.click(await screen.findByRole('tab', { name: 'Review 2' }))

    expect(within(screen.getByRole('region', { name: 'Ready to complete' })).getByText('Ready one')).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Overdue' })).getByText('Late one')).toBeInTheDocument()
    expect(screen.queryByText('Soon one')).not.toBeInTheDocument()
  })

  it('no longer shows an Overdue group under Scheduled', async () => {
    mockData([makeTask({ due_date: '2020-01-01' })])
    render(<TasksScreen />)

    await screen.findByRole('tab', { name: 'Scheduled 0' })

    expect(screen.queryByRole('region', { name: 'Overdue' })).not.toBeInTheDocument()
  })
})

describe('TasksScreen paging', () => {
  const many = (count: number) =>
    Array.from({ length: count }, (_, index) =>
      makeTask({ id: `t${index}`, title: `Task ${index}`, due_date: null }),
    )

  it('loads 50 tasks and offers to load the rest', async () => {
    mockData(many(60))
    render(<TasksScreen />)
    await userEvent.click(await screen.findByRole('tab', { name: 'Someday 60' }))

    expect(await screen.findByRole('button', { name: 'Load 10 more' })).toBeInTheDocument()
    expect(screen.getAllByRole('article')).toHaveLength(50)
  })

  it('loads the next page on request', async () => {
    mockData(many(60))
    render(<TasksScreen />)
    await userEvent.click(await screen.findByRole('tab', { name: 'Someday 60' }))

    await userEvent.click(await screen.findByRole('button', { name: /Load \d+ more/ }))

    expect(await screen.findByText('Task 59')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Load \d+ more/ })).not.toBeInTheDocument()
  })

  it('takes counts from the server, not from loaded tasks', async () => {
    mockData(many(120))
    render(<TasksScreen />)

    expect(await screen.findByRole('tab', { name: 'Someday 120' })).toBeInTheDocument()
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

    expect(await screen.findByRole('dialog', { name: 'Every step is done' })).toBeInTheDocument()
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

describe('Step order', () => {
  it('no longer labels a step as Next', async () => {
    mockData([makeTask({ due_date: TODAY })])
    render(<TasksScreen />)

    await userEvent.click(await screen.findByRole('button', { name: /Show steps/ }))

    expect(screen.queryByText('Next', { exact: true })).not.toBeInTheDocument()
  })

  it('moves a step with the keyboard', async () => {
    const task = makeTask({ due_date: TODAY })
    mockData([task])
    mockApi.PUT.mockReturnValue(ok(task))
    render(<TasksScreen />)
    await userEvent.click(await screen.findByRole('button', { name: /Show steps/ }))

    screen.getByRole('button', { name: /Reorder step “Find the policy”/ }).focus()
    await userEvent.keyboard('{ArrowDown}')

    expect(mockApi.PUT).toHaveBeenCalledWith('/tasks/{task_id}/steps/order', {
      params: { path: { task_id: 't1' } },
      body: { step_ids: ['s2', 's1'] },
    })
  })
})

describe('Editing and history', () => {
  const postponed = makeTask({ due_date: TODAY, postpone_count: 3, postponement_reasons: { blocked: 2, dreading: 1 } })

  it('says why a task was postponed', async () => {
    mockData([postponed])
    render(<TasksScreen />)

    expect(await screen.findByText('Postponed 3 times: 2 blocked, 1 dreading')).toBeInTheDocument()
  })

  it('keeps the history hidden until asked for', async () => {
    mockData([postponed])
    render(<TasksScreen />)

    await userEvent.click(await screen.findByRole('button', { name: /Show steps/ }))

    expect(screen.getByRole('button', { name: 'Show postponement history' })).toHaveAttribute(
      'aria-expanded',
      'false',
    )
    expect(screen.queryByRole('heading', { name: 'History' })).not.toBeInTheDocument()
  })

  it('shows the history, newest first, when asked', async () => {
    mockData([postponed])
    render(<TasksScreen />)
    await userEvent.click(await screen.findByRole('button', { name: /Show steps/ }))

    await userEvent.click(screen.getByRole('button', { name: 'Show postponement history' }))

    await screen.findByRole('heading', { name: 'History' })
    const history = Array.from(document.querySelectorAll('.history-entry'))
    expect(history[0]).toHaveTextContent('Moved to Someday')
    expect(history[1]).toHaveTextContent('“Waiting on Sam”')
  })

  it('links to the guide for a reason that keeps coming back', async () => {
    mockData([postponed])
    render(<TasksScreen />)

    await userEvent.click(await screen.findByRole('button', { name: /Show steps/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Show postponement history' }))

    expect(await screen.findByRole('button', { name: "Read: When something's in the way" })).toBeInTheDocument()
  })

  it('opens the edit dialog', async () => {
    mockData([postponed])
    render(<TasksScreen />)

    await userEvent.click(await screen.findByRole('button', { name: 'Edit “Renew insurance”' }))

    expect(screen.getByRole('dialog', { name: 'Edit task' })).toBeInTheDocument()
  })
})

describe('Repeating tasks', () => {
  it('say how they repeat', async () => {
    mockData([makeTask({ title: 'Run 20 min', due_date: TODAY, repeat: { frequency: 'weekly', weekdays: [0, 3], day_of_month: null, until: null } })])
    render(<TasksScreen />)

    expect(await screen.findByText('Repeats Mon, Thu')).toBeInTheDocument()
  })
})

describe('Finished tasks', () => {
  const finished = makeTask({ status: 'done', steps: [{ id: 's1', text: 'Only', done: true }] })

  it('offer no way to add, remove or reorder steps', async () => {
    mockData([finished])
    render(<TasksScreen />)
    await userEvent.click(await screen.findByRole('tab', { name: /Done/ }))

    await userEvent.click(await screen.findByRole('button', { name: /Show steps/ }))

    expect(screen.queryByRole('textbox', { name: /Add a step/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Remove step/ })).not.toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Only' })).toBeDisabled()
  })
})

describe('New task', () => {
  it('creates a task with its steps, goal and time limit', async () => {
    mockData([])
    mockApi.POST.mockReturnValue(ok(makeTask()))
    render(<TasksScreen />)

    await userEvent.click(await screen.findByRole('button', { name: 'New task' }))
    const form = screen.getByRole('form', { name: 'New task' })
    await userEvent.type(within(form).getByRole('textbox', { name: 'Task' }), 'Renew insurance')
    await userEvent.type(within(form).getByRole('textbox', { name: 'Step 1' }), 'Find the policy')
    await userEvent.click(within(form).getByRole('button', { name: '+ Add step' }))
    await userEvent.type(within(form).getByRole('textbox', { name: 'Step 2' }), 'Call the broker')
    await userEvent.selectOptions(within(form).getByRole('combobox', { name: 'Goal' }), 'Essentials')
    await userEvent.type(within(form).getByRole('spinbutton', { name: 'Time limit amount' }), '1.5')
    await userEvent.selectOptions(within(form).getByRole('combobox', { name: 'Time limit unit' }), 'hours')
    await userEvent.click(within(form).getByRole('button', { name: 'Add task' }))

    expect(mockApi.POST).toHaveBeenCalledWith('/tasks', {
      body: {
        title: 'Renew insurance',
        steps: ['Find the policy', 'Call the broker'],
        goal_id: 'g1',
        time_limit_minutes: 90,
        due_date: null,
        repeat: null,
      },
    })
  })

  it('creates a new goal inline', async () => {
    mockData([])
    mockApi.POST.mockReturnValue(ok({ ...GOALS[0], id: 'g2', title: 'Fitness' }))
    render(<TasksScreen />)

    await userEvent.click(await screen.findByRole('button', { name: 'New task' }))
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Goal' }), '+ New goal…')
    await userEvent.type(screen.getByRole('textbox', { name: 'New goal name' }), 'Fitness')
    await userEvent.click(screen.getByRole('button', { name: 'Create' }))

    expect(mockApi.POST).toHaveBeenCalledWith('/goals', { body: { title: 'Fitness' } })
  })

  it('requires a first step', async () => {
    mockData([])
    render(<TasksScreen />)

    await userEvent.click(await screen.findByRole('button', { name: 'New task' }))

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
