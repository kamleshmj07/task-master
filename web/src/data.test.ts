import type { RoutineRead } from '@task-master/api-client'
import { describe, expect, it } from 'vitest'

import { describeSchedule } from '@/data'
import { addDays, isoDate } from '@/dates'

function routine(overrides: Partial<RoutineRead>): RoutineRead {
  return {
    id: 'r',
    goal_id: null,
    title: 'R',
    estimate_minutes: null,
    frequency: 'daily',
    weekdays: null,
    day_of_month: null,
    start_date: '2026-01-01',
    end_date: '2026-12-31',
    created_at: '',
    updated_at: '',
    ...overrides,
  }
}

describe('describeSchedule', () => {
  it('describes daily routines', () => {
    expect(describeSchedule(routine({}))).toBe('Every day')
  })

  it('lists weekly days', () => {
    expect(describeSchedule(routine({ frequency: 'weekly', weekdays: [0, 2, 4] }))).toBe(
      'Mon, Wed, Fri',
    )
  })

  it('explains the monthly fallback', () => {
    expect(describeSchedule(routine({ frequency: 'monthly', day_of_month: 31 }))).toBe(
      'Monthly on day 31 (or the last day)',
    )
  })
})

describe('dates', () => {
  it('formats local dates as ISO', () => {
    expect(isoDate(new Date(2026, 0, 5))).toBe('2026-01-05')
  })

  it('adds days across month ends', () => {
    expect(addDays('2026-01-31', 1)).toBe('2026-02-01')
  })
})
