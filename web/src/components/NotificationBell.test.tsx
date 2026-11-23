import type { NotificationRead } from '@task-master/api-client'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { NotificationBell } from '@/components/NotificationBell'
import { NavigationContext } from '@/navigation'
import { announceNotificationsChanged, timeAgo } from '@/notifications'
import { findA11yViolations } from '@/test/axe'
import { mockApi, ok } from '@/test/mockApi'

vi.mock('@/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api')>()),
  api: (await import('@/test/mockApi')).mockApi,
}))

function notification(overrides: Partial<NotificationRead> = {}): NotificationRead {
  return {
    id: 'n1',
    kind: 'goal_deadline',
    title: '“Ship” is due in 3 days',
    body: 'The deadline is Wed 25 Nov. Check what is left to do.',
    goal_id: 'g1',
    created_at: new Date().toISOString(),
    read: false,
    ...overrides,
  }
}

/** The server: `check` reports the unread count, lists return `items`. */
function mockServer(items: NotificationRead[]) {
  const unread = () => ({ unread: items.filter((item) => !item.read).length })
  mockApi.POST.mockImplementation((path: string) => ok(path === '/notifications/check' ? unread() : {}))
  mockApi.GET.mockImplementation((path: string) =>
    ok(path === '/notifications/unread-count' ? unread() : items),
  )
}

function renderBell() {
  const go = vi.fn()
  const view = render(
    <NavigationContext.Provider value={{ go }}>
      <NotificationBell />
    </NavigationContext.Provider>,
  )
  return { go, ...view }
}

const openBell = async () => userEvent.click(await screen.findByRole('button', { name: /Notifications/ }))

beforeEach(() => {
  for (const verb of Object.values(mockApi)) verb.mockReset()
})

describe('NotificationBell', () => {
  it('checks for new notifications when the app opens', async () => {
    mockServer([notification()])
    renderBell()

    expect(await screen.findByRole('button', { name: 'Notifications, 1 unread' })).toBeInTheDocument()
    expect(mockApi.POST).toHaveBeenCalledWith('/notifications/check')
  })

  it('lists title and explanation when opened', async () => {
    mockServer([notification()])
    renderBell()

    await openBell()

    expect(await screen.findByText('“Ship” is due in 3 days')).toBeInTheDocument()
    expect(screen.getByText(/Check what is left to do/)).toBeInTheDocument()
  })

  it('takes a goal notification to Goals and marks it read', async () => {
    mockServer([notification()])
    const { go } = renderBell()
    await openBell()

    await userEvent.click(await screen.findByRole('button', { name: 'Open goals' }))

    expect(mockApi.POST).toHaveBeenCalledWith('/notifications/{notification_id}/read', {
      params: { path: { notification_id: 'n1' } },
    })
    expect(go).toHaveBeenCalledWith('goals')
  })

  it('takes the due-soon summary to Tasks', async () => {
    mockServer([notification({ kind: 'tasks_due_soon', title: '3 tasks are due in the next 3 days', goal_id: null })])
    const { go } = renderBell()
    await openBell()

    await userEvent.click(await screen.findByRole('button', { name: 'Review tasks' }))

    expect(go).toHaveBeenCalledWith('tasks')
  })

  it('marks one as read without leaving', async () => {
    mockServer([notification()])
    const { go } = renderBell()
    await openBell()

    await userEvent.click(await screen.findByRole('button', { name: 'Mark ““Ship” is due in 3 days” as read' }))

    expect(mockApi.POST).toHaveBeenCalledWith('/notifications/{notification_id}/read', {
      params: { path: { notification_id: 'n1' } },
    })
    expect(go).not.toHaveBeenCalled()
  })

  it('marks all as read', async () => {
    mockServer([notification()])
    renderBell()
    await openBell()

    await userEvent.click(await screen.findByRole('button', { name: 'Mark all as read' }))

    expect(mockApi.POST).toHaveBeenCalledWith('/notifications/read-all')
  })

  it('says you are caught up when there is nothing', async () => {
    mockServer([])
    renderBell()
    await openBell()

    expect(await screen.findByText(/You're all caught up/)).toBeInTheDocument()
  })

  it('refreshes the count when told notifications changed', async () => {
    mockServer([])
    renderBell()
    await screen.findByRole('button', { name: 'Notifications' })
    mockServer([notification()])

    announceNotificationsChanged()

    expect(await screen.findByRole('button', { name: 'Notifications, 1 unread' })).toBeInTheDocument()
  })

  it('has no accessibility violations when open', async () => {
    mockServer([notification(), notification({ id: 'n2', read: true })])
    const { container } = renderBell()
    await openBell()
    await screen.findAllByText('“Ship” is due in 3 days')

    expect(await findA11yViolations(container)).toEqual([])
  })
})

describe('timeAgo', () => {
  const now = new Date('2026-11-22T12:00:00Z')

  it.each([
    ['2026-11-22T11:59:40Z', 'just now'],
    ['2026-11-22T11:55:00Z', '5 min ago'],
    ['2026-11-22T09:00:00Z', '3 h ago'],
    ['2026-11-20T12:00:00Z', '2 d ago'],
  ])('formats %s as %j', (iso, label) => {
    expect(timeAgo(iso, now)).toBe(label)
  })
})
