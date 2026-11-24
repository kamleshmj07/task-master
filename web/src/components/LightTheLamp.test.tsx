import type { OnboardingRead } from '@task-master/api-client'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { LightTheLamp } from '@/components/LightTheLamp'
import { findA11yViolations } from '@/test/axe'
import { mockApi, ok } from '@/test/mockApi'

vi.mock('@/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api')>()),
  api: (await import('@/test/mockApi')).mockApi,
}))

const NOTHING: OnboardingRead = { goal: null, task: null, three: false, routine: null, finished: false }
const HALFWAY: OnboardingRead = {
  ...NOTHING,
  goal: { id: 'g1', title: 'Run a 10k' },
  task: { id: 't1', title: 'Buy running shoes', first_step: 'Look up three shoe shops' },
}
const ALL_LIT: OnboardingRead = { ...HALFWAY, three: true, routine: { id: 'r1', title: 'Take a walk' } }

function renderLamp(state: OnboardingRead) {
  const handlers = {
    onChanged: vi.fn(),
    onAddToThree: vi.fn(),
    onFinish: vi.fn(),
    onReadTips: vi.fn(),
    onHide: vi.fn(),
  }
  const view = render(<LightTheLamp state={state} name="Ada" {...handlers} />)
  return { ...handlers, ...view }
}

beforeEach(() => {
  for (const verb of Object.values(mockApi)) verb.mockReset()
  mockApi.POST.mockReturnValue(ok({}))
})

describe('Light the lamp', () => {
  it('starts unlit, with the first step open', () => {
    renderLamp(NOTHING)

    expect(screen.getByRole('img', { name: 'Lamp, 0 of 4 rays lit' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Your goal' })).toBeInTheDocument()
  })

  it('fills the goal from an idea and creates it', async () => {
    const { onChanged } = renderLamp(NOTHING)

    await userEvent.click(screen.getByRole('button', { name: 'Learn Spanish' }))
    await userEvent.click(screen.getByRole('button', { name: 'Set goal' }))

    expect(mockApi.POST).toHaveBeenCalledWith('/goals', { body: { title: 'Learn Spanish' } })
    expect(onChanged).toHaveBeenCalled()
  })

  it('adds a task with its first step under the new goal', async () => {
    renderLamp({ ...NOTHING, goal: { id: 'g1', title: 'Run a 10k' } })

    await userEvent.type(screen.getByRole('textbox', { name: 'Task' }), 'Buy running shoes')
    await userEvent.type(screen.getByRole('textbox', { name: 'Its first step' }), 'Look up shops')
    await userEvent.click(screen.getByRole('button', { name: 'Add task' }))

    expect(mockApi.POST).toHaveBeenCalledWith('/tasks', {
      body: { title: 'Buy running shoes', steps: ['Look up shops'], goal_id: 'g1' },
    })
  })

  it('shows what each finished step made, and lights a ray for it', () => {
    renderLamp(HALFWAY)

    expect(screen.getByRole('img', { name: 'Lamp, 2 of 4 rays lit' })).toBeInTheDocument()
    expect(screen.getByText('Buy running shoes. First step: Look up three shoe shops')).toBeInTheDocument()
    expect(screen.getByText('A first step that small is the hardest part done.')).toBeInTheDocument()
  })

  it('offers the new task for the three', async () => {
    const { onAddToThree } = renderLamp(HALFWAY)

    await userEvent.click(screen.getByRole('button', { name: 'Add “Buy running shoes” to your three' }))

    expect(onAddToThree).toHaveBeenCalledWith('t1')
  })

  it('adds a daily routine', async () => {
    renderLamp({ ...HALFWAY, three: true })

    await userEvent.type(screen.getByRole('textbox', { name: 'Your routine' }), 'Take a walk')
    await userEvent.click(screen.getByRole('button', { name: 'Add routine' }))

    expect(mockApi.POST).toHaveBeenCalledWith(
      '/routines',
      expect.objectContaining({ body: expect.objectContaining({ title: 'Take a walk', frequency: 'daily' }) }),
    )
  })

  it('welcomes the user once all four are lit', async () => {
    const { onFinish } = renderLamp(ALL_LIT)

    expect(screen.getByRole('heading', { name: 'Your lamp is on, Ada' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Start my day' }))

    expect(onFinish).toHaveBeenCalled()
  })

  it('can be put off for today', async () => {
    const { onHide } = renderLamp(NOTHING)

    await userEvent.click(screen.getByRole('button', { name: 'Not now' }))

    expect(onHide).toHaveBeenCalled()
  })

  it.each([
    ['unlit', NOTHING],
    ['halfway', HALFWAY],
    ['lit', ALL_LIT],
  ])('has no accessibility violations when %s', async (_, state) => {
    const { container } = renderLamp(state)

    expect(await findA11yViolations(container)).toEqual([])
  })
})
