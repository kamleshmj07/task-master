import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { EditTaskDialog } from '@/screens/EditTaskDialog'
import { findA11yViolations } from '@/test/axe'
import { makeGoal, makeTask } from '@/test/fixtures'
import { mockApi, ok } from '@/test/mockApi'

vi.mock('@/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api')>()),
  api: (await import('@/test/mockApi')).mockApi,
}))

const TASK = makeTask({ title: 'Renew insurance', due_date: '2099-01-10', time_limit_minutes: 90, goal_id: 'g1' })

function renderDialog(task = TASK) {
  const handlers = { onSaved: vi.fn(), onDeleted: vi.fn(), onClose: vi.fn() }
  const view = render(<EditTaskDialog task={task} goals={[makeGoal()]} {...handlers} />)
  return { ...handlers, ...view }
}

beforeEach(() => {
  for (const verb of Object.values(mockApi)) verb.mockReset()
  mockApi.PATCH.mockReturnValue(ok(TASK))
  mockApi.DELETE.mockReturnValue(ok(undefined))
})

describe('EditTaskDialog', () => {
  it('starts with the task as it is', () => {
    renderDialog()

    expect(screen.getByLabelText('Task')).toHaveValue('Renew insurance')
    expect(screen.getByLabelText('Goal')).toHaveValue('g1')
    expect(screen.getByRole('spinbutton', { name: 'Time limit amount' })).toHaveValue(1.5)
    expect(screen.getByRole('combobox', { name: 'Time limit unit' })).toHaveValue('hours')
  })

  it('only lets the due date move earlier', () => {
    renderDialog()

    expect(screen.getByLabelText('Due date')).toHaveAttribute('max', '2099-01-10')
  })

  it('saves the edits, leaving an unchanged date alone', async () => {
    const { onSaved } = renderDialog()

    await userEvent.clear(screen.getByLabelText('Task'))
    await userEvent.type(screen.getByLabelText('Task'), 'Renew car insurance')
    await userEvent.selectOptions(screen.getByLabelText('Goal'), 'No goal')
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(mockApi.PATCH).toHaveBeenCalledWith('/tasks/{task_id}', {
      params: { path: { task_id: 't1' } },
      body: { title: 'Renew car insurance', goal_id: null, time_limit_minutes: 90 },
    })
    expect(onSaved).toHaveBeenCalled()
  })

  it('sends a date brought forward', async () => {
    renderDialog()

    await userEvent.clear(screen.getByLabelText('Due date'))
    await userEvent.type(screen.getByLabelText('Due date'), '2099-01-05')
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(mockApi.PATCH.mock.calls[0]?.[1].body.due_date).toBe('2099-01-05')
  })

  it('asks before deleting', async () => {
    renderDialog()

    await userEvent.click(screen.getByRole('button', { name: 'Delete task' }))

    expect(screen.getByRole('dialog', { name: 'Delete this task?' })).toHaveTextContent('2 steps')
    expect(mockApi.DELETE).not.toHaveBeenCalled()
  })

  it('deletes after confirming', async () => {
    const { onDeleted } = renderDialog()
    await userEvent.click(screen.getByRole('button', { name: 'Delete task' }))

    await userEvent.click(screen.getByRole('button', { name: 'Delete task' }))

    expect(mockApi.DELETE).toHaveBeenCalledWith('/tasks/{task_id}', { params: { path: { task_id: 't1' } } })
    expect(onDeleted).toHaveBeenCalled()
  })

  it('keeps the task when the deletion is cancelled', async () => {
    renderDialog()
    await userEvent.click(screen.getByRole('button', { name: 'Delete task' }))

    await userEvent.click(screen.getByRole('button', { name: 'Keep it' }))

    expect(screen.getByRole('dialog', { name: 'Edit task' })).toBeInTheDocument()
    expect(mockApi.DELETE).not.toHaveBeenCalled()
  })

  it('has no accessibility violations', async () => {
    const { container } = renderDialog()

    expect(await findA11yViolations(container)).toEqual([])
  })
})
