import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AddCardDrawer, CardDrawer } from './AddCardDrawer'

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

  it('показывает доступность сбора для выбранной площадки', async () => {
    const user = userEvent.setup()
    render(
      <QueryClientProvider client={new QueryClient()}>
        <AddCardDrawer open onClose={vi.fn()} />
      </QueryClientProvider>,
    )
    await user.click(screen.getByRole('radio', { name: /Wildberries/ }))
    expect(screen.getByRole('radio', { name: /Wildberries/ })).toBeChecked()
    expect(screen.queryByLabelText('Код размера WB')).not.toBeInTheDocument()
    await user.click(screen.getByRole('radio', { name: /AliExpress/ }))
    expect(screen.getByRole('radio', { name: /AliExpress/ })).toBeChecked()
    await user.click(screen.getByRole('radio', { name: /Яндекс Маркет/ }))
    expect(screen.getByRole('radio', { name: /Яндекс Маркет/ })).toBeChecked()
    expect(screen.getByPlaceholderText('https://market.yandex.ru/product/...')).toBeInTheDocument()
  })
})


it.each([
  ['Ozon', 'ID карточки', '123', 'https://www.ozon.ru/product/123/', 'ozon'],
  ['Wildberries', 'Артикул WB', '123', 'https://www.wildberries.ru/catalog/123/detail.aspx', 'wildberries'],
  ['AliExpress', 'ID товара', '123', 'https://aliexpress.ru/item/123.html', 'aliexpress'],
])('добавляет %s по артикулу или товарной ссылке без SKU', async (label, field, article, url, marketplace) => {
  const user = userEvent.setup()
  const onSave = vi.fn().mockResolvedValue(undefined)
  const onClose = vi.fn()
  render(<CardDrawer open onClose={onClose} onSave={onSave} isPending={false} />)
  await user.click(screen.getByRole('radio', { name: new RegExp(label) }))
  expect(screen.queryByLabelText('Код размера WB')).not.toBeInTheDocument()
  expect(screen.queryByLabelText('SKU варианта')).not.toBeInTheDocument()
  await user.type(screen.getByLabelText(field), article)
  expect(screen.getByRole('button', { name: 'Добавить' })).toBeEnabled()
  await user.type(screen.getByLabelText('URL'), url)
  await user.click(screen.getByRole('button', { name: 'Добавить' }))
  expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ marketplace, externalId: article, url }))
  expect(onClose).toHaveBeenCalledOnce()
})

it.each([
  ['Ozon', 'ID карточки', 'https://www.ozon.ru/product/kedy-123/', 'Ссылка не соответствует артикулу выбранного варианта Ozon'],
  ['Wildberries', 'Артикул WB', 'https://www.wildberries.ru/catalog/123/detail.aspx?size=456', 'Ссылка не соответствует артикулу WB'],
  ['AliExpress', 'ID товара', 'https://aliexpress.ru/item/123.html?sku_id=456', 'Ссылка не соответствует ID товара'],
])('извлекает артикул %s из ссылки с SKU и проверяет принадлежность товара', async (label, field, url, error) => {
  const user = userEvent.setup()
  const onSave = vi.fn()
  render(<CardDrawer open onClose={vi.fn()} onSave={onSave} isPending={false} />)
  await user.click(screen.getByRole('radio', { name: new RegExp(label) }))
  await user.type(screen.getByLabelText('URL'), url)
  expect(screen.getByLabelText(field)).toHaveValue('123')
  await user.clear(screen.getByLabelText(field))
  await user.type(screen.getByLabelText(field), '999')
  await user.click(screen.getByRole('button', { name: 'Добавить' }))
  expect(screen.getByText(error)).toBeInTheDocument()
  expect(onSave).not.toHaveBeenCalled()
})
