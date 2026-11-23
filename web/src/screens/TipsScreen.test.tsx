import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { TipsScreen } from '@/screens/TipsScreen'
import { findA11yViolations } from '@/test/axe'
import { TIP_ARTICLES } from '@/tips'

describe('TipsScreen', () => {
  it('lists a guide for every postpone reason', () => {
    render(<TipsScreen />)

    expect(screen.getAllByRole('button')).toHaveLength(TIP_ARTICLES.length)
  })

  it('opens and focuses the guide it was sent to', () => {
    render(<TipsScreen initialTip="blocked" />)

    expect(screen.getByRole('heading', { level: 2, name: "When something's in the way" })).toHaveFocus()
  })

  it('switches guides', async () => {
    render(<TipsScreen />)

    await userEvent.click(screen.getByRole('button', { name: /When you don't want to do it/ }))

    expect(screen.getByRole('heading', { level: 2, name: "When you don't want to do it" })).toBeInTheDocument()
  })

  it('shows before-and-after examples', () => {
    render(<TipsScreen initialTip="stuck" />)

    expect(screen.getByRole('cell', { name: 'Download Form 16 from the employer portal' })).toBeInTheDocument()
  })

  it('has no accessibility violations', async () => {
    const { container } = render(<TipsScreen />)

    expect(await findA11yViolations(container)).toEqual([])
  })
})
