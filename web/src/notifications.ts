const CHANGED = 'task-master:notifications-changed'

/** Tell the bell that notifications changed, e.g. after a postponement. */
export function announceNotificationsChanged(): void {
  window.dispatchEvent(new Event(CHANGED))
}

/** Run `listener` whenever notifications change; returns the unsubscribe. */
export function onNotificationsChanged(listener: () => void): () => void {
  window.addEventListener(CHANGED, listener)
  return () => window.removeEventListener(CHANGED, listener)
}

/** "just now", "5 min ago", "3 h ago", "2 d ago". */
export function timeAgo(iso: string, now: Date = new Date()): string {
  const minutes = Math.floor((now.getTime() - new Date(iso).getTime()) / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  return `${Math.floor(hours / 24)} d ago`
}
