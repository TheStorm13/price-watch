import { act, render, screen, cleanup } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, expect, it, vi } from 'vitest'
import type { CollectionRun, CatalogSnapshot } from '../../types/domain'
import { CollectionProvider, useCollection } from './CollectionProvider'
import { api } from '../../api/client'
import { queryKeys } from '../../api/queries'
import { NOTIFICATIONS_KEY } from './dealNotifications'

vi.mock('../../api/client', () => ({ isDesktopMode: false, api: {
  getCatalog: vi.fn(), getRun: vi.fn(), listRuns: vi.fn(), startRun: vi.fn(), retryRun: vi.fn(), continueRun: vi.fn(),
} }))
function Observer() {
  const state = useCollection()
  return <><span data-testid="run">{state.run?.id ?? 'closed'}</span><span data-testid="notice">{state.dealNotice ?? 'none'}</span></>
}
afterEach(() => { cleanup(); vi.useRealTimers(); vi.resetAllMocks(); localStorage.clear() })
it('loads fresh catalog after terminal state and retries after panel dismissal', async () => {
  vi.useFakeTimers()
  localStorage.setItem('price-watch-active-run', '99')
  const run: CollectionRun = { id: 99, status: 'completed', totalCount: 1, successCount: 1, failureCount: 0,
    current: null, challenge: null, startedAt: new Date().toISOString(), finishedAt: new Date().toISOString(),
    retryableCount: 0, retryScopeIncomplete: false }
  const catalog: CatalogSnapshot = { cards: [], groups: [], deals: [{
    card: { id: 1, marketplace: 'ozon', externalId: '1', title: 'Item', url: null, imageUrl: null,
      tags: [], dealsEnabled: true, currentPrice: "80.00", currentAvailability: 'in_stock',
      minimumPrice: "80.00", averagePrice: "100.00", lastObservedAt: '2026-10-22', createdAt: '2026-10-01', updatedAt: '2026-10-22' },
    averagePrice: "100.00", savings: "20.00", baselineDays: 1, lastCollectionRunId: 99 }] }
  vi.mocked(api.getRun).mockResolvedValue(run)
  vi.mocked(api.listRuns).mockResolvedValue([run])
  vi.mocked(api.getCatalog).mockRejectedValueOnce(new Error('offline')).mockRejectedValueOnce(new Error('offline')).mockResolvedValue(catalog)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 15_000 } } })
  // This cached snapshot is fresh by staleTime but predates terminal observation.
  client.setQueryData(queryKeys.catalog, { cards: [], groups: [], deals: [] })
  render(<QueryClientProvider client={client}><CollectionProvider><Observer /></CollectionProvider></QueryClientProvider>)
  for (let i = 0; i < 8; i++) await act(async () => { await vi.advanceTimersByTimeAsync(10) })
  expect(api.getCatalog).toHaveBeenCalledTimes(1)
  expect(JSON.parse(localStorage.getItem(NOTIFICATIONS_KEY)!)).toMatchObject({ pending: [99], processed: 0 })
  await act(async () => { await vi.advanceTimersByTimeAsync(2_100) })
  expect(screen.getByTestId('run')).toHaveTextContent('closed')
  expect(screen.getByTestId('notice')).toHaveTextContent('none')
  await act(async () => { await vi.advanceTimersByTimeAsync(1_100) })
  expect(screen.getByTestId('notice')).toHaveTextContent('1')
  expect(api.getCatalog).toHaveBeenCalledTimes(3)
  cleanup(); client.clear()
})

it('exposes continuation failure, disables duplicate requests, and clears failure on retry', async () => {
  const { fireEvent, waitFor } = await import('@testing-library/react')
  const run: CollectionRun = { id: 99, status: 'waiting_for_user', totalCount: 5, successCount: 1, failureCount: 0,
    current: null, challenge: null, startedAt: new Date().toISOString(), finishedAt: null,
    retryableCount: 0, retryScopeIncomplete: false }
  localStorage.setItem('price-watch-active-run', '99')
  vi.mocked(api.getRun).mockResolvedValue(run)
  vi.mocked(api.listRuns).mockResolvedValue([run])
  let resume!: (value: CollectionRun) => void
  vi.mocked(api.continueRun).mockRejectedValueOnce(new Error('Продолжение недоступно'))
    .mockImplementationOnce(() => new Promise((resolve) => { resume = resolve }))
  function Controls() {
    const state = useCollection()
    return <><button disabled={state.isContinuing} onClick={state.continueRun}>Продолжить</button><span role="status">{state.continueError}</span></>
  }
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><CollectionProvider><Controls /></CollectionProvider></QueryClientProvider>)
  await waitFor(() => expect(api.getRun).toHaveBeenCalled())
  fireEvent.click(screen.getByRole('button', { name: 'Продолжить' }))
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Продолжение недоступно'))
  fireEvent.click(screen.getByRole('button', { name: 'Продолжить' }))
  await waitFor(() => expect(screen.getByRole('button')).toBeDisabled())
  fireEvent.click(screen.getByRole('button'))
  expect(api.continueRun).toHaveBeenCalledTimes(2)
  expect(screen.getByRole('status')).toBeEmptyDOMElement()
  await act(async () => resume({ ...run, status: 'running' }))
  await waitFor(() => expect(screen.getByRole('button')).toBeEnabled())
  expect(screen.getByRole('status')).toBeEmptyDOMElement()
  cleanup(); client.clear()
})
