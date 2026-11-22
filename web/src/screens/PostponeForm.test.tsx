import type { PostponeResponse, TaskRead } from '@task-master/api-client'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { PostponeForm, SuggestionCard } from '@/screens/PostponeForm'
import { findA11yViolations } from '@/test/axe'
import { fail, mockApi, ok } from '@/test/mockApi'

vi.mock('@/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api')>()),
  api: (await import('@/test/mockApi')).mockApi,
}))

const TASK: TaskRead = {
  id: 't1',
  goal_id: null,
  title: 'Write report',
  next_action: 'Open the doc',
  estimate_minutes: 30,
  due_date: '2099-01-10',
  status: 'todo',
  postpone_count: 0,
  completed_at: null,
  created_at: '2026-11-22T00:00:00Z',
  updated_at: '2026-11-22T00:00:00Z',
}

function renderForm() {
  const onPostponed = vi.fn()
  const view = render(<PostponeForm task={TASK} onPostponed={onPostponed} onCancel={vi.fn()} />)
  return { onPostponed, ...view }
}

beforeEach(() => {
  mockApi.POST.mockReset()
})

describe('PostponeForm', () => {
  it('requires a reason before postponing', async () => {
    renderForm()

    await userEvent.click(screen.getByRole('button', { name: 'Postpone' }))

    expect(screen.getByRole('alert')).toHaveTextContent('Pick a reason first.')
  })

  it('asks for a note only when the reason is other', async () => {
    renderForm()

    await userEvent.click(screen.getByRole('radio', { name: 'Other…' }))

    expect(screen.getByRole('textbox', { name: "What's going on?" })).toBeRequired()
  })

  it('defaults to the day after the current due date', () => {
    renderForm()

    expect(screen.getByLabelText('New date')).toHaveValue('2099-01-11')
  })

  it('sends a dated postponement', async () => {
    mockApi.POST.mockReturnValue(ok({}))
    renderForm()

    await userEvent.click(screen.getByRole('radio', { name: "I don't know where to start" }))
    await userEvent.click(screen.getByRole('button', { name: 'Postpone' }))

    expect(mockApi.POST).toHaveBeenCalledWith('/tasks/{task_id}/postpone', {
      params: { path: { task_id: 't1' } },
      body: { reason: 'stuck', to_date: '2099-01-11', note: null },
    })
  })

  it('moves to Someday without a date', async () => {
    mockApi.POST.mockReturnValue(ok({}))
    renderForm()

    await userEvent.click(screen.getByRole('radio', { name: "Something's in the way" }))
    await userEvent.click(screen.getByRole('checkbox', { name: /Move to Someday/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Postpone' }))

    expect(mockApi.POST.mock.calls[0]?.[1].body.to_date).toBeNull()
  })

  it('shows the API error', async () => {
    mockApi.POST.mockReturnValue(fail({ detail: 'A finished task cannot be postponed' }))
    renderForm()

    await userEvent.click(screen.getByRole('radio', { name: "I don't want to do it" }))
    await userEvent.click(screen.getByRole('button', { name: 'Postpone' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'A finished task cannot be postponed',
    )
  })

  it('has no accessibility violations', async () => {
    const { container } = renderForm()

    expect(await findA11yViolations(container)).toEqual([])
  })
})

describe('SuggestionCard', () => {
  const result = {
    suggestion: {
      headline: 'Clear the way',
      actions: ['Write down what you are waiting on'],
      reflection: 'Is it really time, or is it dread?',
    },
  } as PostponeResponse

  it('shows the fix and the reflection prompt', () => {
    render(<SuggestionCard result={result} onDismiss={vi.fn()} />)

    expect(screen.getByRole('complementary', { name: 'Suggested fix' })).toHaveTextContent(
      'Is it really time, or is it dread?',
    )
  })
})
