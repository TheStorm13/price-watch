import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { AddCardDrawer, CardDrawer } from './AddCardDrawer'

afterEach(cleanup)

it('rejects nonnumeric articles', async () => {
  const user = userEvent.setup()
  render(<QueryClientProvider client={new QueryClient()}><AddCardDrawer open onClose={vi.fn()} /></QueryClientProvider>)
  await user.type(screen.getByLabelText('Артикул'), 'ozon-123')
  await user.click(screen.getByRole('button', { name: 'Добавить' }))
  expect(screen.getByText('Введите числовой ID карточки Ozon')).toBeInTheDocument()
})

it.each([
  ['Ozon', 'Артикул', 'ozon'], ['Wildberries', 'Артикул WB', 'wildberries'],
  ['AliExpress', 'ID товара', 'aliexpress'], ['Яндекс Маркет', 'Артикул', 'yandex-market'],
])('adds %s by article with optional title and comma separated tags', async (label, field, marketplace) => {
  const user = userEvent.setup()
  const onSave = vi.fn().mockResolvedValue(undefined)
  render(<CardDrawer open onClose={vi.fn()} onSave={onSave} isPending={false} />)
  await user.click(screen.getByRole('radio', { name: new RegExp(label) }))
  expect(screen.getByRole('button', { name: 'Артикул' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByRole('button', { name: 'Ссылка' })).toBeDisabled()
  expect(screen.queryByLabelText('URL')).not.toBeInTheDocument()
  await user.type(screen.getByLabelText(field), '123')
  await user.type(screen.getByLabelText('Теги (до двух, через запятую)'), 'кухня, подарок')
  await user.click(screen.getByRole('button', { name: 'Добавить' }))
  expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ marketplace, externalId: '123', title: null, url: null, tags: ['кухня', 'подарок'] }))
})

it('explains optional title on demand and restores keyboard focus', async () => {
  const user = userEvent.setup()
  render(<CardDrawer open onClose={vi.fn()} onSave={vi.fn()} isPending={false} />)
  expect(screen.queryByText(/Можно оставить пустым/)).not.toBeInTheDocument()
  const help = screen.getByRole('button', { name: 'Справка: Название' })
  help.focus()
  await user.keyboard('{Enter}')
  expect(screen.getByText('Можно оставить пустым — название появится после обновления цен.')).toBeVisible()
  await user.keyboard('{Escape}')
  expect(help).toHaveFocus()
  expect(screen.getByLabelText('Название (необязательно)')).toHaveValue('')
})
