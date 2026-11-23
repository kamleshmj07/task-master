import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { Field } from '@/components/Field'
import { InfoTip } from '@/components/InfoTip'
import { findA11yViolations } from '@/test/axe'

describe('InfoTip', () => {
  it('hides the explanation until asked', () => {
    render(<InfoTip label="Time limit">The most time in total.</InfoTip>)

    expect(screen.queryByRole('note')).not.toBeInTheDocument()
  })

  it('shows the explanation on click', async () => {
    render(<InfoTip label="Time limit">The most time in total.</InfoTip>)

    await userEvent.click(screen.getByRole('button', { name: 'About Time limit' }))

    expect(screen.getByRole('note')).toHaveTextContent('The most time in total.')
  })

  it('hides it again on Escape', async () => {
    render(<InfoTip label="Time limit">The most time in total.</InfoTip>)
    await userEvent.click(screen.getByRole('button', { name: 'About Time limit' }))

    await userEvent.keyboard('{Escape}')

    expect(screen.queryByRole('note')).not.toBeInTheDocument()
  })
})

describe('Field', () => {
  it('labels its control and offers info beside the label', () => {
    render(
      <Field label="Due date" info="Leave empty for Someday.">
        {(id) => <input id={id} type="date" />}
      </Field>,
    )

    expect(screen.getByLabelText('Due date')).toHaveAttribute('type', 'date')
    expect(screen.getByRole('button', { name: 'About Due date' })).toBeInTheDocument()
  })

  it('has no accessibility violations with the info open', async () => {
    const { container } = render(
      <Field label="Due date" info="Leave empty for Someday.">
        {(id) => <input id={id} type="date" />}
      </Field>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'About Due date' }))

    expect(await findA11yViolations(container)).toEqual([])
  })
})
