import type { PostponeReason } from '@task-master/api-client'
import { createContext, useContext } from 'react'

export type ScreenName = 'today' | 'tasks' | 'routines' | 'goals' | 'tips' | 'settings'

/** Move between screens; `tip` opens one guide on the Tips page. */
export interface Navigation {
  go: (screen: ScreenName, options?: { tip?: PostponeReason }) => void
}

export const NavigationContext = createContext<Navigation>({ go: () => undefined })

export function useNavigation(): Navigation {
  return useContext(NavigationContext)
}
