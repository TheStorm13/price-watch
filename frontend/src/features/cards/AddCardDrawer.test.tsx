import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AddCardDrawer } from './AddCardDrawer'

afterEach(cleanup)

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

  it('позволяет выбрать площадку без коннектора', async () => {
    const user = userEvent.setup()
    render(
      <QueryClientProvider client={new QueryClient()}>
        <AddCardDrawer open onClose={vi.fn()} />
      </QueryClientProvider>,
    )
    await user.click(screen.getByRole('radio', { name: /Wildberries/ }))
    expect(screen.getByRole('radio', { name: /Wildberries/ })).toBeChecked()
    expect(screen.getByText('Укажите название: автоматический сбор пока недоступен')).toBeInTheDocument()
    await user.click(screen.getByRole('radio', { name: /AliExpress/ }))
    expect(screen.getByRole('radio', { name: /AliExpress/ })).toBeChecked()
  })
})
