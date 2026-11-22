import type { NotificationRead } from '@task-master/api-client'
import { useCallback, useEffect, useRef, useState } from 'react'

import { api } from '@/api'
import { onNotificationsChanged, timeAgo } from '@/notifications'

/** Top-bar bell: unread badge, and a panel of saved tips to mark as read. */
export function NotificationBell() {
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
    void loadCount()
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

  async function handleMarkRead(id: string) {
    await api.POST('/notifications/{notification_id}/read', {
      params: { path: { notification_id: id } },
    })
    await Promise.all([loadItems(), loadCount()])
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
          {items?.length === 0 && <p className="muted panel-empty">Nothing yet. Tips you get when postponing are kept here.</p>}
          <ul className="list panel-list">
            {items?.map((item) => (
              <li key={item.id} className={item.read ? 'note' : 'note unread'}>
                {!item.read && <span className="unread-dot" aria-hidden="true" />}
                <div className="grow stack-xs">
                  <p className="small muted">
                    Tip for “{item.task_title}”, {timeAgo(item.created_at)}
                  </p>
                  <p className="title">{item.headline}</p>
                  <ul className="note-actions">
                    {item.actions.map((action) => (
                      <li key={action}>{action}</li>
                    ))}
                  </ul>
                  {item.reflection && <p className="reflection small">{item.reflection}</p>}
                </div>
                {!item.read && (
                  <button
                    type="button"
                    className="ghost"
                    aria-label={`Mark “${item.headline}” as read`}
                    onClick={() => void handleMarkRead(item.id)}
                  >
                    Mark read
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
