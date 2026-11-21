import { describe, expect, it } from '@jest/globals'
import { render, screen } from '@testing-library/react-native'

import { App } from '@/App'

describe('App', () => {
  it('shows the product name as a header', async () => {
    await render(<App />)

    expect(screen.getByRole('header', { name: 'Task Master' })).toBeTruthy()
  })
})
