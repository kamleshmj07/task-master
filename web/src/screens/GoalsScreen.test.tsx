import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { addDays, todayIso } from '@/dates'
import { GoalsScreen } from '@/screens/GoalsScreen'
import { findA11yViolations } from '@/test/axe'
import { makeGoal } from '@/test/fixtures'
import { mockApi, ok } from '@/test/mockApi'

vi.mock('@/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api')>()),
  api: (await import('@/test/mockApi')).mockApi,
}))

const TODAY = todayIso()

const MARATHON = makeGoal({
  id: 'g2',
  title: 'Run a marathon',
  why: 'Prove I can',
  deadline: addDays(TODAY, 5),
  progress: {
    total_tasks: 7,
    done_tasks: 4,
    next_due_task: { id: 't1', title: '15 km long run', due_date: addDays(TODAY, 3) },
    last_moved_at: `${addDays(TODAY, -40)}T09:00:00Z`,
  },
})

beforeEach(() => {
  for (const verb of Object.values(mockApi)) verb.mockReset()
  mockApi.GET.mockReturnValue(ok([MARATHON, makeGoal({ id: 'g3', title: 'Old idea', status: 'archived' })]))
  mockApi.PATCH.mockReturnValue(ok(MARATHON))
  mockApi.DELETE.mockReturnValue(ok(undefined))
})

const card = async () => (await screen.findByRole('heading', { name: 'Run a marathon' })).closest('li') as HTMLElement

describe('GoalsScreen progress', () => {
  it('shows tasks done out of the total', async () => {
    render(<GoalsScreen />)

    expect(within(await card()).getByText('4 of 7 tasks done')).toBeInTheDocument()
    expect(within(await card()).getByRole('progressbar')).toHaveAttribute('aria-valuenow', '57')
  })

  it('flags a deadline within a week', async () => {
    render(<GoalsScreen />)

    expect(within(await card()).getByText(/5 days left/)).toHaveClass('loss')
  })

  it('names the next task due', async () => {
    render(<GoalsScreen />)

    expect(within(await card()).getByText(/Next due: 15 km long run/)).toBeInTheDocument()
  })

  it('says nothing about routines, which stand alone', async () => {
    render(<GoalsScreen />)

    expect(within(await card()).queryByText(/routine/)).not.toBeInTheDocument()
  })

  it('says when an active goal has been quiet for 30 days or more', async () => {
    render(<GoalsScreen />)

    expect(within(await card()).getByText('Quiet for 40 days')).toBeInTheDocument()
  })

  it('groups goals by status', async () => {
    render(<GoalsScreen />)

    expect(await screen.findByRole('region', { name: 'Archived goals' })).toHaveTextContent('Old idea')
  })

  it('has no accessibility violations', async () => {
    const { container } = render(<GoalsScreen />)
    await card()

    expect(await findA11yViolations(container)).toEqual([])
  })
})

describe('GoalsScreen editing', () => {
  it('opens the goal in an edit dialog with its values', async () => {
    render(<GoalsScreen />)

    await userEvent.click(await screen.findByRole('button', { name: 'Edit “Run a marathon”' }))

    const dialog = screen.getByRole('dialog', { name: 'Edit goal' })
    expect(within(dialog).getByLabelText('Goal')).toHaveValue('Run a marathon')
    expect(within(dialog).getByLabelText('Why it matters')).toHaveValue('Prove I can')
  })

  it('saves title, why, deadline and status', async () => {
    render(<GoalsScreen />)
    await userEvent.click(await screen.findByRole('button', { name: 'Edit “Run a marathon”' }))
    const dialog = screen.getByRole('dialog', { name: 'Edit goal' })

    await userEvent.clear(within(dialog).getByLabelText('Goal'))
    await userEvent.type(within(dialog).getByLabelText('Goal'), 'Run a half')
    await userEvent.selectOptions(within(dialog).getByLabelText('Status'), 'Completed')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save changes' }))

    expect(mockApi.PATCH).toHaveBeenCalledWith('/goals/{goal_id}', {
      params: { path: { goal_id: 'g2' } },
      body: { title: 'Run a half', why: 'Prove I can', deadline: addDays(TODAY, 5), status: 'completed' },
    })
  })
})

describe('GoalsScreen deleting', () => {
  it('asks first, saying how much goes with it', async () => {
    render(<GoalsScreen />)

    await userEvent.click(await screen.findByRole('button', { name: 'Delete “Run a marathon”' }))

    const dialog = screen.getByRole('dialog', { name: 'Delete this goal?' })
    expect(dialog).toHaveTextContent('7 tasks')
    expect(dialog).not.toHaveTextContent('routine')
    expect(mockApi.DELETE).not.toHaveBeenCalled()
  })

  it('deletes only after confirming', async () => {
    render(<GoalsScreen />)
    await userEvent.click(await screen.findByRole('button', { name: 'Delete “Run a marathon”' }))

    await userEvent.click(screen.getByRole('button', { name: 'Delete goal and its tasks' }))

    expect(mockApi.DELETE).toHaveBeenCalledWith('/goals/{goal_id}', { params: { path: { goal_id: 'g2' } } })
  })

  it('can be cancelled', async () => {
    render(<GoalsScreen />)
    await userEvent.click(await screen.findByRole('button', { name: 'Delete “Run a marathon”' }))

    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(mockApi.DELETE).not.toHaveBeenCalled()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
