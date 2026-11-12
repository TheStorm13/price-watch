import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { TargetNotificationObserver } from './TargetNotificationObserver'
const data = vi.hoisted(() => ({
  settings: { instanceId: 'db-a', targetNotificationsEnabled: true },
  catalog: { instanceId: 'db-a', cards: [{ id: 1, primaryVariantId: 2, targetPrice: '100', currentPrice: '101', currentAvailability: 'in_stock', lastObservedAt: '2026-11-01', lastCollectionRunId: 1 }] },
  fetching: false,
  send: vi.fn(),
}))
vi.mock('../../api/queries', () => ({ catalogOptions: {}, usePurchaseSettings: () => ({ data: data.settings }) }))
vi.mock('@tanstack/react-query', () => ({ useQuery: () => ({ data: data.catalog, isFetching: data.fetching }) }))
vi.mock('./notificationTransport', () => ({ notifyTarget: (...args: unknown[]) => data.send(...args) }))
afterEach(() => { cleanup(); localStorage.clear(); vi.clearAllMocks(); data.settings = { instanceId: 'db-a', targetNotificationsEnabled: true }; data.fetching = false
  data.catalog = { instanceId: 'db-a', cards: [{ id: 1, primaryVariantId: 2, targetPrice: '100', currentPrice: '101', currentAvailability: 'in_stock', lastObservedAt: '2026-11-01', lastCollectionRunId: 1 }] } })
function lower() { data.catalog = { ...data.catalog, cards: data.catalog.cards.map(c => ({ ...c, currentPrice: '99', lastObservedAt: '2026-11-02', lastCollectionRunId: 2 })) } }
it('observes outside catalog routes, persists checkpoint, reports transport errors without retrying', async () => {
  data.send.mockRejectedValue(new Error('transport denied'))
  const view = render(<><h1>Детали товара</h1><TargetNotificationObserver /></>)
  expect(data.send).not.toHaveBeenCalled()
  lower(); view.rerender(<><h1>Детали товара</h1><TargetNotificationObserver /></>)
  await waitFor(() => expect(data.send).toHaveBeenCalledOnce())
  expect(await screen.findByRole('alert')).toHaveTextContent('transport denied')
  expect(JSON.parse(localStorage.getItem('price-watch-target-notifications-v1:db-a')!)['1:2']).toMatchObject({ reached: true, runId: 2 })
  data.catalog = structuredClone(data.catalog); view.rerender(<><h1>Детали товара</h1><TargetNotificationObserver /></>)
  expect(data.send).toHaveBeenCalledOnce()
})
it('baselines restart, enable, target edits and a different backend without an alert burst', () => {
  data.send.mockResolvedValue(undefined)
  const view = render(<TargetNotificationObserver />)
  data.settings = { ...data.settings, targetNotificationsEnabled: false }; view.rerender(<TargetNotificationObserver />)
  lower(); view.rerender(<TargetNotificationObserver />)
  data.settings = { ...data.settings, targetNotificationsEnabled: true }; view.rerender(<TargetNotificationObserver />)
  data.settings = { ...data.settings, instanceId: 'db-b' }; data.catalog = { ...data.catalog, instanceId: 'db-b' }; view.rerender(<TargetNotificationObserver />)
  expect(data.send).not.toHaveBeenCalled()
  expect(localStorage.getItem('price-watch-target-notifications-v1:db-b')).not.toBeNull()
  view.unmount(); render(<TargetNotificationObserver />)
  expect(data.send).not.toHaveBeenCalled()
})
it('does not baseline cached catalog while a startup fetch is in progress or instances mismatch', () => {
  data.fetching = true
  const view = render(<TargetNotificationObserver />)
  lower(); data.fetching = false; view.rerender(<TargetNotificationObserver />)
  expect(data.send).not.toHaveBeenCalled()
  expect(localStorage.getItem('price-watch-target-notifications-v1:db-a')).not.toBeNull()
  data.settings = { ...data.settings, instanceId: 'db-c' }; view.rerender(<TargetNotificationObserver />)
  expect(localStorage.getItem('price-watch-target-notifications-v1:db-c')).toBeNull()
  data.catalog = { ...data.catalog, instanceId: 'db-c' }; view.rerender(<TargetNotificationObserver />)
  expect(data.send).not.toHaveBeenCalled()
  expect(localStorage.getItem('price-watch-target-notifications-v1:db-c')).not.toBeNull()
})
