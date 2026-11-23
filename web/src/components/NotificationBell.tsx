import type { NotificationRead } from '@task-master/api-client'
import { useCallback, useEffect, useRef, useState } from 'react'

import { api } from '@/api'
import { type ScreenName, useNavigation } from '@/navigation'
import { onNotificationsChanged, timeAgo } from '@/notifications'

/** Where each kind of notification sends you, and what the button says. */
const DESTINATIONS: Record<NotificationRead['kind'], { screen: ScreenName; action: string }> = {
  goal_deadline: { screen: 'goals', action: 'Open goals' },
  goal_done: { screen: 'goals', action: 'Open goals' },
  goal_stale: { screen: 'goals', action: 'Open goals' },
  tasks_due_soon: { screen: 'tasks', action: 'Review tasks' },
}

/**
 * Top-bar bell. When the app opens it asks the server to create any
 * notifications now due (goal updates, tasks coming due), then shows them.
 */
export function NotificationBell() {
  const { go } = useNavigation()
  const [open, setOpen] = useState(false)
  const [unread, setUnread] = useState(0)
  const [items, setItems] = useState<NotificationRead[] | null>(null)
  const ref = useRef<HTMLDivElement>(null)

  const loadCount = useCallback(async () => {
    const { data } = await api.GET('/notifications/unread-count')
    setUnread(data?.unread ?? 0)
  }, [])

  const loadItems = useCallback(async () => {
    const { data } = await api.GET('/notifications', { params: { query: { limit: 50 } } })
    setItems(data ?? [])
  }, [])

  useEffect(() => {
    void (async () => {
      const { data } = await api.POST('/notifications/check')
      setUnread(data?.unread ?? 0)
    })()
    return onNotificationsChanged(() => void loadCount())
  }, [loadCount])

  useEffect(() => {
    if (!open) return
    void loadItems()
    const handleClick = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open, loadItems])

  async function markRead(id: string) {
    await api.POST('/notifications/{notification_id}/read', {
      params: { path: { notification_id: id } },
    })
  }

  async function handleMarkRead(id: string) {
    await markRead(id)
    await Promise.all([loadItems(), loadCount()])
  }

  async function handleOpen(item: NotificationRead) {
    if (!item.read) await markRead(item.id)
    setOpen(false)
    void loadCount()
    go(DESTINATIONS[item.kind].screen)
  }

  async function handleMarkAllRead() {
    await api.POST('/notifications/read-all')
    await Promise.all([loadItems(), loadCount()])
  }

  const label = unread > 0 ? `Notifications, ${unread} unread` : 'Notifications'
  return (
    <div
      className="bell"
      ref={ref}
      onKeyDown={(event) => {
        if (event.key === 'Escape') setOpen(false)
      }}
    >
      <button
        type="button"
        className="ghost icon"
        aria-label={label}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
          <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
        </svg>
        {unread > 0 && (
          <span className="badge" aria-hidden="true">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="bell-panel" role="dialog" aria-label="Notifications">
          <div className="row between panel-head">
            <h2>Notifications</h2>
            {unread > 0 && (
              <button type="button" className="ghost accent" onClick={() => void handleMarkAllRead()}>
                Mark all as read
              </button>
            )}
          </div>
          {items?.length === 0 && (
            <p className="muted panel-empty">
              You're all caught up. Goal updates and tasks coming due will show up here.
            </p>
          )}
          <ul className="list panel-list">
            {items?.map((item) => (
              <li key={item.id} className={item.read ? 'note' : 'note unread'}>
                {!item.read && <span className="unread-dot" aria-hidden="true" />}
                <div className="grow stack-xs">
                  <p className="title">{item.title}</p>
                  <p className="small muted">{item.body}</p>
                  <p className="small muted">{timeAgo(item.created_at)}</p>
                  <div className="row note-buttons">
                    <button type="button" className="small-button" onClick={() => void handleOpen(item)}>
                      {DESTINATIONS[item.kind].action}
                    </button>
                    {!item.read && (
                      <button
                        type="button"
                        className="ghost small-button"
                        aria-label={`Mark “${item.title}” as read`}
                        onClick={() => void handleMarkRead(item.id)}
                      >
                        Mark read
                      </button>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
