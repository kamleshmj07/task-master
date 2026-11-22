import type { PostponeResponse } from '@task-master/api-client'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { PostponeDialog, SuggestionCard } from '@/screens/PostponeForm'
import { findA11yViolations } from '@/test/axe'
import { makeTask } from '@/test/fixtures'
import { fail, mockApi, ok } from '@/test/mockApi'

vi.mock('@/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api')>()),
  api: (await import('@/test/mockApi')).mockApi,
}))

const TASK = makeTask({ due_date: '2099-01-10' })

function renderDialog() {
  const onPostponed = vi.fn()
  const onClose = vi.fn()
  const view = render(<PostponeDialog task={TASK} onPostponed={onPostponed} onClose={onClose} />)
  return { onPostponed, onClose, ...view }
}

beforeEach(() => {
  mockApi.POST.mockReset()
})

describe('PostponeDialog', () => {
  it('opens as a labelled dialog', () => {
    renderDialog()

    expect(screen.getByRole('dialog', { name: 'Why are you putting this off?' })).toBeInTheDocument()
  })

  it('offers the reasons as buttons', () => {
    renderDialog()

    expect(screen.getAllByRole('button', { pressed: false })).toHaveLength(4)
  })

  it('requires a reason before postponing', async () => {
    renderDialog()

    await userEvent.click(screen.getByRole('button', { name: 'Postpone' }))

    expect(screen.getByRole('alert')).toHaveTextContent('Pick a reason first.')
  })

  it('marks the chosen reason as pressed', async () => {
    renderDialog()

    await userEvent.click(screen.getByRole('button', { name: "I don't want to do it" }))

    expect(screen.getByRole('button', { name: "I don't want to do it" })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('asks for a note only when the reason is other', async () => {
    renderDialog()

    await userEvent.click(screen.getByRole('button', { name: 'Other…' }))

    expect(screen.getByRole('textbox', { name: "What's going on?" })).toBeRequired()
  })

  it('defaults to the day after the current due date', () => {
    renderDialog()

    expect(screen.getByLabelText('New date')).toHaveValue('2099-01-11')
  })

  it('sends a dated postponement', async () => {
    mockApi.POST.mockReturnValue(ok({}))
    renderDialog()

    await userEvent.click(screen.getByRole('button', { name: "I don't know where to start" }))
    await userEvent.click(screen.getByRole('button', { name: 'Postpone' }))

    expect(mockApi.POST).toHaveBeenCalledWith('/tasks/{task_id}/postpone', {
      params: { path: { task_id: 't1' } },
      body: { reason: 'stuck', to_date: '2099-01-11', note: null },
    })
  })

  it('moves to Someday without a date', async () => {
    mockApi.POST.mockReturnValue(ok({}))
    renderDialog()

    await userEvent.click(screen.getByRole('button', { name: "Something's in the way" }))
    await userEvent.click(screen.getByRole('checkbox', { name: /Move to Someday/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Postpone' }))

    expect(mockApi.POST.mock.calls[0]?.[1].body.to_date).toBeNull()
  })

  it('shows the API error', async () => {
    mockApi.POST.mockReturnValue(fail({ detail: 'A finished task cannot be postponed' }))
    renderDialog()

    await userEvent.click(screen.getByRole('button', { name: "I don't want to do it" }))
    await userEvent.click(screen.getByRole('button', { name: 'Postpone' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('A finished task cannot be postponed')
  })

  it('closes on Escape', async () => {
    const { onClose } = renderDialog()

    await userEvent.keyboard('{Escape}')

    expect(onClose).toHaveBeenCalled()
  })

  it('has no accessibility violations', async () => {
    const { container } = renderDialog()

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
