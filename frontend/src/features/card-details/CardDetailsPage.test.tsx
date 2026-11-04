import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { CardDetailsPage } from './CardDetailsPage'

const state = vi.hoisted(() => ({ chartError: false, historyError: false, historyLoading: false, chartLoading: false, primaryVariantId: 1, variantStatistics: false }))
const card = { id: 1, title: 'Проверяемый товар', marketplace: 'ozon', externalId: '123', tags: [], dealsEnabled: true,
  imageUrl: null, url: null, currentPrice: '100.00', currentAvailability: 'in_stock', lastObservedAt: '2026-10-29', updatedAt: '2026-10-29' }
vi.mock('../../api/queries', () => ({
  useCard: () => ({ data: { ...card, primaryVariantId: state.primaryVariantId, currentPrice: state.primaryVariantId === 2 ? '200.00' : card.currentPrice }, isLoading: false, isError: false }),
  useCardHistory: (_cardId: number, _days: number, _page: number, variantId?: number) => ({
    data: state.variantStatistics && variantId === 2 ? undefined : { history: [], statistics: state.variantStatistics ? {minimumPrice:'100.00',maximumPrice:'120.00'} : {} },
    isLoading: state.historyLoading || (state.variantStatistics && variantId === 2), isError: state.historyError, refetch: vi.fn(),
  }),
  useCardChart: () => ({ data: { points: [] }, isLoading: state.chartLoading, isError: state.chartError, refetch: vi.fn() }),
  useCardVariants: () => ({ data: [], isLoading: false, isError: false }),
  useVariantTracking: () => ({ isPending: false }),
  useUpdateCard: () => ({ isPending: false }), useDeleteCard: () => ({}),
}))
vi.mock('../collection/CollectionProvider', () => ({ useCollectionCommands: () => ({ isStarting: false, startError: null }) }))
vi.mock('./VariantPriceChart', () => ({ VariantPriceChart: () => <div>График доступен</div> }))
afterEach(() => { cleanup(); Object.assign(state, { chartError: false, historyError: false, historyLoading: false, chartLoading: false, primaryVariantId: 1, variantStatistics: false }) })
function view() { return render(<MemoryRouter initialEntries={['/cards/1']}><Routes><Route path="/cards/:cardId" element={<CardDetailsPage />} /></Routes></MemoryRouter>) }
it('keeps the card and measurements visible when chart fails', () => {
  state.chartError = true; view()
  expect(screen.getByRole('heading', { name: 'Проверяемый товар' })).toBeVisible()
  expect(screen.getByRole('alert')).toHaveTextContent('Не удалось загрузить график')
  expect(screen.getByRole('table', { name: 'История измерений цены' })).toBeVisible()
})
it('keeps chart and current price visible when history fails', () => {
  state.historyError = true; view()
  expect(screen.getByText('100 ₽', { exact: true })).toBeVisible()
  expect(screen.getByText('График доступен')).toBeVisible()
  expect(screen.getByRole('alert')).toHaveTextContent('Не удалось загрузить измерения')
})
it('keeps card actions visible while the independent sections load', () => {
  state.historyLoading = true; state.chartLoading = true; view()
  expect(screen.getByRole('heading', { name: 'Проверяемый товар' })).toBeVisible()
  expect(screen.getByRole('button', { name: 'Обновить эту карточку' })).toBeEnabled()
  expect(screen.getByLabelText('Загрузка графика')).toBeVisible()
  expect(screen.getByLabelText('Загрузка измерений')).toBeVisible()
})

it('does not show the previous SKU statistics while a new primary history loads', () => {
  state.variantStatistics = true
  const {container, rerender} = view()
  expect(container.querySelector('.price-stat')).toHaveTextContent('100 ₽')
  state.primaryVariantId = 2
  rerender(<MemoryRouter initialEntries={['/cards/1']}><Routes><Route path="/cards/:cardId" element={<CardDetailsPage />} /></Routes></MemoryRouter>)
  expect(container.querySelector('.price-summary__primary')).toHaveTextContent('200 ₽')
  expect(container.querySelector('.price-stat')).toHaveTextContent('—')
  expect(screen.getByLabelText('Загрузка измерений')).toBeVisible()
})
