import type { OnboardingRead } from '@task-master/api-client'

/** The goal every account starts with; it does not count as the user's own. */
export const DEFAULT_GOAL_TITLE = 'Essentials'

export const GOAL_IDEAS = ['Run a 10k', 'Learn Spanish', 'Sort my finances', 'Finish my portfolio'] as const
export const ROUTINE_IDEAS = ['Take a walk', 'Drink a glass of water', 'Read for 10 minutes'] as const

/** Which of the four setup steps are done, in order. */
export function setupSteps(state: OnboardingRead): boolean[] {
  return [state.goal !== null, state.task !== null, state.three, state.routine !== null]
}

const HIDDEN_KEY = 'task-master:lamp-hidden'

/** Whether "Not now" hid the setup card for `day`. Browser storage may be off. */
export function isHiddenFor(day: string): boolean {
  try {
    return window.localStorage.getItem(HIDDEN_KEY) === day
  } catch {
    return false
  }
}

export function hideFor(day: string): void {
  try {
    window.localStorage.setItem(HIDDEN_KEY, day)
  } catch {
    // Without storage, the card simply stays hidden until the page reloads.
  }
}
