import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { App } from '@/App'
import { findA11yViolations } from '@/test/axe'

describe('App', () => {
  it('shows the product name as the main heading', () => {
    render(<App />)

    expect(
      screen.getByRole('heading', { level: 1, name: 'Task Master' }),
    ).toBeInTheDocument()
  })

  it('has no accessibility violations', async () => {
    const { container } = render(<App />)

    expect(await findA11yViolations(container)).toEqual([])
  })
})
