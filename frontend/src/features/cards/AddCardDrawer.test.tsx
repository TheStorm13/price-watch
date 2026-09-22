import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AddCardDrawer } from './AddCardDrawer'

describe('AddCardDrawer', () => {
  it('показывает ошибку для нечислового Ozon ID', async () => {
    const user = userEvent.setup()
    render(
      <QueryClientProvider client={new QueryClient()}>
        <AddCardDrawer open onClose={vi.fn()} />
      </QueryClientProvider>,
    )
    await user.type(screen.getByLabelText(/ID карточки/), 'ozon-123')
    await user.click(screen.getByRole('button', { name: 'Добавить' }))
    expect(screen.getByText('Введите числовой ID карточки Ozon')).toBeInTheDocument()
  })
})
