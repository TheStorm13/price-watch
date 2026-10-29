import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { CardDetailsPage } from './CardDetailsPage'

const state = vi.hoisted(() => ({ chartError: false, historyError: false, historyLoading: false, chartLoading: false }))
const card = { id: 1, title: 'Проверяемый товар', marketplace: 'ozon', externalId: '123', tags: [], dealsEnabled: true,
  imageUrl: null, url: null, currentPrice: '100.00', currentAvailability: 'in_stock', lastObservedAt: '2026-10-29', updatedAt: '2026-10-29' }
vi.mock('../../api/queries', () => ({
  useCard: () => ({ data: card, isLoading: false, isError: false }),
  useCardHistory: () => ({ data: { history: [], statistics: {} }, isLoading: state.historyLoading, isError: state.historyError, refetch: vi.fn() }),
  useCardChart: () => ({ data: { points: [] }, isLoading: state.chartLoading, isError: state.chartError, refetch: vi.fn() }),
  useUpdateCard: () => ({ isPending: false }), useDeleteCard: () => ({}),
}))
vi.mock('../collection/CollectionProvider', () => ({ useCollection: () => ({ isStarting: false, startError: null }) }))
vi.mock('./PriceChart', () => ({ PriceChart: () => <div>График доступен</div> }))
afterEach(() => { cleanup(); Object.assign(state, { chartError: false, historyError: false, historyLoading: false, chartLoading: false }) })
function view() { render(<MemoryRouter initialEntries={['/cards/1']}><Routes><Route path="/cards/:cardId" element={<CardDetailsPage />} /></Routes></MemoryRouter>) }
it('keeps the card and measurements visible when chart fails', () => {
  state.chartError = true; view()
  expect(screen.getByRole('heading', { name: 'Проверяемый товар' })).toBeVisible()
  expect(screen.getByRole('alert')).toHaveTextContent('Не удалось загрузить график')
  expect(screen.getByRole('table')).toBeVisible()
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
