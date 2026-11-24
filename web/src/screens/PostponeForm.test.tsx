import type { PostponeResponse } from '@task-master/api-client'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { addDays, todayIso } from '@/dates'
import { NavigationContext } from '@/navigation'
import { PostponeDialog, TipDialog } from '@/screens/PostponeForm'
import { findA11yViolations } from '@/test/axe'
import { makeTask } from '@/test/fixtures'
import { fail, mockApi, ok } from '@/test/mockApi'

vi.mock('@/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api')>()),
  api: (await import('@/test/mockApi')).mockApi,
}))

const TODAY = todayIso()

function renderDialog(dueDate: string | null = null) {
  const onPostponed = vi.fn()
  const onClose = vi.fn()
  const task = makeTask({ due_date: dueDate })
  const view = render(<PostponeDialog task={task} onPostponed={onPostponed} onClose={onClose} />)
  return { onPostponed, onClose, ...view }
}

const reasons = () => within(screen.getByRole('group', { name: 'Reason' }))
const moveTo = () => within(screen.getByRole('group', { name: 'Move it to' }))

beforeEach(() => {
  mockApi.POST.mockReset()
})

describe('PostponeDialog reasons', () => {
  it('opens as a labelled dialog', () => {
    renderDialog()

    expect(screen.getByRole('dialog', { name: 'Why are you putting this off?' })).toBeInTheDocument()
  })

  it('explains each reason and previews its fix', () => {
    renderDialog()

    const stuck = reasons().getByRole('button', { name: /I don't know where to start/ })
    expect(stuck).toHaveTextContent('Unclear, or too big')
    expect(stuck).toHaveTextContent("We'll help you shrink the first step")
  })

  it('offers four reasons', () => {
    renderDialog()

    expect(reasons().getAllByRole('button')).toHaveLength(4)
  })

  it('requires a reason before postponing', async () => {
    renderDialog()

    await userEvent.click(screen.getByRole('button', { name: 'Postpone' }))

    expect(screen.getByRole('alert')).toHaveTextContent('Pick a reason first.')
  })

  it('marks the chosen reason as pressed', async () => {
    renderDialog()

    await userEvent.click(reasons().getByRole('button', { name: /I don't want to do it/ }))

    expect(reasons().getByRole('button', { name: /I don't want to do it/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('asks for a note only when the reason is other', async () => {
    renderDialog()

    await userEvent.click(reasons().getByRole('button', { name: /Other/ }))

    expect(screen.getByRole('textbox', { name: "What's going on?" })).toBeRequired()
  })
})

describe('PostponeDialog dates', () => {
  it('defaults to tomorrow', () => {
    renderDialog()

    expect(moveTo().getByRole('button', { name: 'Tomorrow' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('disables quick dates that would not move the task later', () => {
    renderDialog(addDays(TODAY, 2))

    expect(moveTo().getByRole('button', { name: 'Tomorrow' })).toBeDisabled()
    expect(moveTo().getByRole('button', { name: 'In 3 days' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('sends the chosen quick date', async () => {
    mockApi.POST.mockReturnValue(ok({}))
    renderDialog()

    await userEvent.click(reasons().getByRole('button', { name: /I don't know where to start/ }))
    await userEvent.click(moveTo().getByRole('button', { name: 'Next week' }))
    await userEvent.click(screen.getByRole('button', { name: 'Postpone' }))

    expect(mockApi.POST).toHaveBeenCalledWith('/tasks/{task_id}/postpone', {
      params: { path: { task_id: 't1' } },
      body: { reason: 'stuck', to_date: addDays(TODAY, 7), note: null },
    })
  })

  it('shows a date field for "Pick a date…"', async () => {
    renderDialog()

    await userEvent.click(moveTo().getByRole('button', { name: 'Pick a date…' }))

    expect(screen.getByLabelText('New date')).toBeInTheDocument()
  })

  it('moves to Someday without a date', async () => {
    mockApi.POST.mockReturnValue(ok({}))
    renderDialog()

    await userEvent.click(reasons().getByRole('button', { name: /Something's in the way/ }))
    await userEvent.click(moveTo().getByRole('button', { name: 'Someday' }))
    await userEvent.click(screen.getByRole('button', { name: 'Postpone' }))

    expect(mockApi.POST.mock.calls[0]?.[1].body.to_date).toBeNull()
  })

  it('shows the API error', async () => {
    mockApi.POST.mockReturnValue(fail({ detail: 'A finished task cannot be postponed' }))
    renderDialog()

    await userEvent.click(reasons().getByRole('button', { name: /I don't want to do it/ }))
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

describe('PostponeDialog for a repeating task', () => {
  function renderRepeating() {
    const task = makeTask({ due_date: TODAY, repeat: { frequency: 'daily', weekdays: null, day_of_month: null, until: null }, series_id: 't1' })
    render(<PostponeDialog task={task} onPostponed={vi.fn()} onClose={vi.fn()} />)
  }

  it('offers skipping to the next run instead of Someday', () => {
    renderRepeating()

    expect(moveTo().getByRole('button', { name: 'Skip to next run' })).toHaveAttribute('aria-pressed', 'true')
    expect(moveTo().queryByRole('button', { name: 'Someday' })).not.toBeInTheDocument()
  })

  it('skips the run with the reason given', async () => {
    mockApi.POST.mockReturnValue(ok({}))
    renderRepeating()

    await userEvent.click(reasons().getByRole('button', { name: /I don't know where to start/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Postpone' }))

    expect(mockApi.POST).toHaveBeenCalledWith('/tasks/{task_id}/skip', {
      params: { path: { task_id: 't1' } },
      body: { reason: 'stuck', note: null },
    })
  })
})

describe('TipDialog', () => {
  function result(reason: 'stuck' | 'blocked'): PostponeResponse {
    return {
      task: makeTask({ title: 'Tax' }),
      postponement: {
        id: 'p1',
        task_id: 't1',
        from_date: null,
        to_date: null,
        reason,
        note: null,
        created_at: '',
      },
      suggestion: {
        headline: 'Clear the way',
        actions: ['Write down what you are waiting on', 'Lower the time limit'],
        reflection: 'Is it really time, or is it dread?',
      },
    }
  }

  function renderTip(reason: 'stuck' | 'blocked', onOpenSteps?: () => void) {
    const go = vi.fn()
    const onDismiss = vi.fn()
    render(
      <NavigationContext.Provider value={{ go }}>
        <TipDialog result={result(reason)} onDismiss={onDismiss} {...(onOpenSteps ? { onOpenSteps } : {})} />
      </NavigationContext.Provider>,
    )
    return { go, onDismiss }
  }

  it('pops up as a dialog named after the fix', () => {
    renderTip('blocked')

    expect(screen.getByRole('dialog', { name: 'Clear the way' })).toBeInTheDocument()
  })

  it('says where the task went', () => {
    renderTip('blocked')

    expect(screen.getByText(/Moved “Tax” to Someday/)).toBeInTheDocument()
  })

  it('lists the fixes as a checklist', () => {
    renderTip('blocked')

    expect(screen.getAllByRole('checkbox')).toHaveLength(2)
  })

  it('shows the reflection prompt', () => {
    renderTip('blocked')

    expect(screen.getByRole('note')).toHaveTextContent('Is it really time, or is it dread?')
  })

  it('no longer mentions notifications', () => {
    renderTip('blocked')

    expect(screen.queryByText(/notifications/i)).not.toBeInTheDocument()
  })

  it('disappears when acknowledged', async () => {
    const { onDismiss } = renderTip('blocked')

    await userEvent.click(screen.getByRole('button', { name: 'Got it' }))

    expect(onDismiss).toHaveBeenCalled()
  })

  it('links to the guide for the reason', async () => {
    const { go, onDismiss } = renderTip('blocked')

    await userEvent.click(screen.getByRole('button', { name: 'Read the guide with examples' }))

    expect(go).toHaveBeenCalledWith('tips', { tip: 'blocked' })
    expect(onDismiss).toHaveBeenCalled()
  })

  it('offers to open the steps when the fix starts there', async () => {
    const onOpenSteps = vi.fn()
    renderTip('stuck', onOpenSteps)

    await userEvent.click(screen.getByRole('button', { name: 'Open steps' }))

    expect(onOpenSteps).toHaveBeenCalled()
  })

  it('does not offer steps for blockers', () => {
    renderTip('blocked', vi.fn())

    expect(screen.queryByRole('button', { name: 'Open steps' })).not.toBeInTheDocument()
  })
})
