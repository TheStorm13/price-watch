import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DealNotifications, NOTIFICATIONS_KEY } from './dealNotifications'
import type { CatalogSnapshot, Deal } from '../../types/domain'

const deal = (runId: number, price = 80): Deal => ({
  card: { id: 1, marketplace: 'ozon', externalId: '1', title: 'Item', url: null, imageUrl: null,
    tags: [], dealsEnabled: true, groupId: null, currentPrice: price, currentAvailability: 'in_stock',
    minimumPrice: price, averagePrice: 100, lastObservedAt: '2026-10-22', createdAt: '2026-10-01', updatedAt: '2026-10-22' },
  averagePrice: 100, savings: 100-price, baselineDays: 1, lastCollectionRunId: runId,
})
const catalog = (runId: number): CatalogSnapshot => ({ cards: [], groups: [], deals: [deal(runId)] })
const queues: DealNotifications[] = []
const create = (fetcher: () => Promise<CatalogSnapshot>, notify = vi.fn()) => {
  const queue = new DealNotifications(localStorage, fetcher, notify)
  queues.push(queue)
  return { queue, notify }
}
beforeEach(() => { vi.useFakeTimers(); localStorage.clear() })
afterEach(() => { queues.splice(0).forEach((q) => q.stop()); vi.useRealTimers() })

describe('durable deal notification work', () => {
  it('retries network failure after the panel would have disappeared and acknowledges only success', async () => {
    const fetcher = vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue(catalog(7))
    const { queue, notify } = create(fetcher)
    queue.start(); queue.enqueue(7)
    await vi.advanceTimersByTimeAsync(0)
    expect(JSON.parse(localStorage.getItem(NOTIFICATIONS_KEY)!)).toMatchObject({ pending: [7], processed: 0 })
    expect(notify).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(2_000)
    expect(notify).toHaveBeenCalledExactlyOnceWith(1)
    queue.enqueue(7)
    await vi.advanceTimersByTimeAsync(60_000)
    expect(fetcher).toHaveBeenCalledTimes(2)
    expect(JSON.parse(localStorage.getItem(NOTIFICATIONS_KEY)!)).toMatchObject({ pending: [], processed: 7 })
  })

  it('retains work enqueued during the request', async () => {
    let resolve!: (value: CatalogSnapshot) => void
    const first = new Promise<CatalogSnapshot>((done) => { resolve = done })
    const fetcher = vi.fn().mockReturnValueOnce(first).mockResolvedValue(catalog(8))
    const { queue, notify } = create(fetcher)
    queue.start(); queue.enqueue(7)
    await vi.advanceTimersByTimeAsync(0)
    queue.enqueue(8)
    resolve(catalog(7))
    await vi.advanceTimersByTimeAsync(0)
    await vi.runOnlyPendingTimersAsync()
    expect(fetcher).toHaveBeenCalledTimes(2)
    expect(notify).toHaveBeenCalledTimes(1) // Same card/price is not a new notification.
    expect(JSON.parse(localStorage.getItem(NOTIFICATIONS_KEY)!)).toMatchObject({ pending: [], processed: 8 })
  })

  it('resumes a failed pending request after remount', async () => {
    const first = create(vi.fn().mockRejectedValue(new Error('offline')))
    first.queue.start(); first.queue.enqueue(5)
    await vi.advanceTimersByTimeAsync(0)
    first.queue.stop()
    const second = create(vi.fn().mockResolvedValue(catalog(5)))
    second.queue.start()
    await vi.advanceTimersByTimeAsync(0)
    expect(second.notify).toHaveBeenCalledExactlyOnceWith(1)
    const third = create(vi.fn().mockResolvedValue(catalog(5)))
    second.queue.stop(); third.queue.start(); third.queue.enqueue(5)
    await vi.advanceTimersByTimeAsync(0)
    expect(third.notify).not.toHaveBeenCalled()
  })

  it('migrates existing acknowledged prices once and tolerates malformed state', async () => {
    localStorage.setItem('price-watch-notified-run', '7')
    localStorage.setItem('price-watch-notified-prices', '{"1":80}')
    const { queue, notify } = create(vi.fn().mockResolvedValue(catalog(8)))
    expect(localStorage.getItem('price-watch-notified-run')).toBeNull()
    queue.start(); queue.enqueue(8)
    await vi.advanceTimersByTimeAsync(0)
    expect(notify).not.toHaveBeenCalled()
    localStorage.setItem(NOTIFICATIONS_KEY, '{broken')
    expect(() => create(vi.fn())).not.toThrow()
  })

  it('ignores results from a stopped generation', async () => {
    let resolve!: (value: CatalogSnapshot) => void
    const old = new Promise<CatalogSnapshot>((done) => { resolve = done })
    const fetcher = vi.fn().mockReturnValueOnce(old).mockResolvedValue(catalog(9))
    const { queue, notify } = create(fetcher)
    queue.start(); queue.enqueue(9)
    await vi.advanceTimersByTimeAsync(0)
    queue.stop(); queue.start()
    await vi.advanceTimersByTimeAsync(0)
    resolve(catalog(9))
    await vi.advanceTimersByTimeAsync(0)
    expect(notify).toHaveBeenCalledTimes(1)
  })
})
