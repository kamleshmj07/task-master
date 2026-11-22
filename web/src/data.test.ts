import { describe, expect, it } from 'vitest'

import { describeSchedule, groupReview, groupScheduled, timeLimitLabel, toMinutes } from '@/data'
import { addDays, daysBetween, dueLabel, isoDate, quickDates } from '@/dates'
import { makeRoutine, makeTask } from '@/test/fixtures'

const TODAY = '2026-11-22'

describe('describeSchedule', () => {
  it('describes daily routines', () => {
    expect(describeSchedule(makeRoutine())).toBe('Every day')
  })

  it('lists weekly days', () => {
    expect(describeSchedule(makeRoutine({ frequency: 'weekly', weekdays: [0, 2, 4] }))).toBe(
      'Mon, Wed, Fri',
    )
  })

  it('explains the monthly fallback', () => {
    expect(describeSchedule(makeRoutine({ frequency: 'monthly', day_of_month: 31 }))).toBe(
      'Monthly on day 31 (or the last day)',
    )
  })
})

describe('timeLimitLabel', () => {
  it.each([
    [null, ''],
    [45, '45 min'],
    [60, '1 hour'],
    [90, '1.5 hours'],
  ])('formats %s as %j', (minutes, label) => {
    expect(timeLimitLabel(minutes)).toBe(label)
  })
})

describe('groupScheduled', () => {
  it('splits tasks into Today, This week and Later, soonest first', () => {
    const tasks = [
      makeTask({ id: 'later', due_date: '2026-12-10' }),
      makeTask({ id: 'week-b', due_date: '2026-11-26' }),
      makeTask({ id: 'today', due_date: TODAY }),
      makeTask({ id: 'week-a', due_date: '2026-11-23' }),
    ]

    const groups = groupScheduled(tasks, TODAY).map((g) => [g.id, g.tasks.map((t) => t.id)])

    expect(groups).toEqual([
      ['today', ['today']],
      ['week', ['week-a', 'week-b']],
      ['later', ['later']],
    ])
  })

  it('leaves out empty groups', () => {
    expect(groupScheduled([makeTask({ due_date: TODAY })], TODAY).map((g) => g.id)).toEqual([
      'today',
    ])
  })
})

describe('groupReview', () => {
  it('puts tasks ready to complete before overdue ones', () => {
    const ready = makeTask({ id: 'ready', steps: [{ id: 's', text: 'x', done: true }] })
    const late = makeTask({ id: 'late', due_date: '2026-11-01' })

    const groups = groupReview([late, ready]).map((g) => [g.id, g.tasks.map((t) => t.id)])

    expect(groups).toEqual([
      ['ready', ['ready']],
      ['overdue', ['late']],
    ])
  })
})

describe('toMinutes', () => {
  it.each([
    ['', 'min', null],
    ['45', 'min', 45],
    ['1.5', 'hours', 90],
    ['0', 'hours', null],
  ] as const)('reads %j %s as %j', (amount, unit, minutes) => {
    expect(toMinutes(amount, unit)).toBe(minutes)
  })
})

describe('quickDates', () => {
  it('offers tomorrow, three days and a week out', () => {
    expect(quickDates(TODAY).map((d) => d.date)).toEqual([
      '2026-11-23',
      '2026-11-25',
      '2026-11-29',
    ])
  })
})

describe('dates', () => {
  it('formats local dates as ISO', () => {
    expect(isoDate(new Date(2026, 0, 5))).toBe('2026-01-05')
  })

  it('adds days across month ends', () => {
    expect(addDays('2026-01-31', 1)).toBe('2026-02-01')
  })

  it('counts days between dates', () => {
    expect(daysBetween('2026-11-22', '2026-12-01')).toBe(9)
  })

  it.each([
    [null, 'Someday'],
    [TODAY, 'Today'],
    ['2026-11-23', 'Tomorrow'],
  ])('labels %s as %j', (iso, label) => {
    expect(dueLabel(iso, TODAY)).toBe(label)
  })

  it('marks overdue dates', () => {
    expect(dueLabel('2026-11-20', TODAY)).toMatch(/^Overdue · /)
  })
})
