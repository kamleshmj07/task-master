import type { NotificationRead } from '@task-master/api-client'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { NotificationBell } from '@/components/NotificationBell'
import { announceNotificationsChanged, timeAgo } from '@/notifications'
import { findA11yViolations } from '@/test/axe'
import { mockApi, ok } from '@/test/mockApi'

vi.mock('@/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api')>()),
  api: (await import('@/test/mockApi')).mockApi,
}))

function tip(overrides: Partial<NotificationRead> = {}): NotificationRead {
  return {
    id: 'n1',
    task_id: 't1',
    task_title: 'Tax',
    reason: 'stuck',
    headline: 'Make the first step smaller',
    actions: ['Split this task'],
    reflection: null,
    created_at: new Date().toISOString(),
    read: false,
    ...overrides,
  }
}

function mockNotifications(items: NotificationRead[]) {
  mockApi.GET.mockImplementation((path: string) =>
    path === '/notifications/unread-count'
      ? ok({ unread: items.filter((item) => !item.read).length })
      : ok(items),
  )
}

beforeEach(() => {
  for (const verb of Object.values(mockApi)) verb.mockReset()
  mockApi.POST.mockReturnValue(ok({}))
})

describe('NotificationBell', () => {
  it('shows the unread count in its label', async () => {
    mockNotifications([tip(), tip({ id: 'n2' })])
    render(<NotificationBell />)

    expect(await screen.findByRole('button', { name: 'Notifications, 2 unread' })).toBeInTheDocument()
  })

  it('lists saved tips when opened', async () => {
    mockNotifications([tip()])
    render(<NotificationBell />)

    await userEvent.click(await screen.findByRole('button', { name: /Notifications/ }))

    expect(await screen.findByText('Make the first step smaller')).toBeInTheDocument()
  })

  it('marks one tip as read', async () => {
    mockNotifications([tip()])
    render(<NotificationBell />)
    await userEvent.click(await screen.findByRole('button', { name: /Notifications/ }))

    await userEvent.click(await screen.findByRole('button', { name: 'Mark “Make the first step smaller” as read' }))

    expect(mockApi.POST).toHaveBeenCalledWith('/notifications/{notification_id}/read', {
      params: { path: { notification_id: 'n1' } },
    })
  })

  it('marks all as read', async () => {
    mockNotifications([tip()])
    render(<NotificationBell />)
    await userEvent.click(await screen.findByRole('button', { name: /Notifications/ }))

    await userEvent.click(await screen.findByRole('button', { name: 'Mark all as read' }))

    expect(mockApi.POST).toHaveBeenCalledWith('/notifications/read-all')
  })

  it('refreshes the count when told notifications changed', async () => {
    mockNotifications([])
    render(<NotificationBell />)
    await screen.findByRole('button', { name: 'Notifications' })
    mockNotifications([tip()])

    announceNotificationsChanged()

    expect(await screen.findByRole('button', { name: 'Notifications, 1 unread' })).toBeInTheDocument()
  })

  it('has no accessibility violations when open', async () => {
    mockNotifications([tip({ reflection: 'Is it dread?' })])
    const { container } = render(<NotificationBell />)
    await userEvent.click(await screen.findByRole('button', { name: /Notifications/ }))
    await screen.findByText('Make the first step smaller')

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
