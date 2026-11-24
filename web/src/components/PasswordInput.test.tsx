import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { PasswordInput } from '@/components/PasswordInput'
import { findA11yViolations } from '@/test/axe'

function renderField(what?: string) {
  return render(
    <div>
      <label htmlFor="pw">Current password</label>
      <PasswordInput id="pw" defaultValue="correct-horse-battery" {...(what ? { what } : {})} />
    </div>,
  )
}

describe('PasswordInput', () => {
  it('hides what was typed at first', () => {
    renderField()

    expect(screen.getByLabelText('Current password')).toHaveAttribute('type', 'password')
  })

  it('shows what was typed with the eye button, and hides it again', async () => {
    renderField()
    const eye = screen.getByRole('button', { name: 'Show password' })

    await userEvent.click(eye)

    expect(screen.getByLabelText('Current password')).toHaveAttribute('type', 'text')
    expect(screen.getByRole('button', { name: 'Hide password' })).toHaveAttribute('aria-pressed', 'true')

    await userEvent.click(screen.getByRole('button', { name: 'Hide password' }))
    expect(screen.getByLabelText('Current password')).toHaveAttribute('type', 'password')
  })

  it('names the button after the field when there are several', () => {
    renderField('current password')

    expect(screen.getByRole('button', { name: 'Show current password' })).toBeInTheDocument()
  })

  it('has no accessibility violations', async () => {
    const { container } = renderField()

    expect(await findA11yViolations(container)).toEqual([])
  })
})
