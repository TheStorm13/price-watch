import { expect, it } from 'vitest'
import type { PriceHistoryPoint } from '../types/domain'
import { priceMetrics } from './mockPriceMetrics'

it('uses prior daily averages, latest ordering and availability like the server', () => {
  const point = (id: number, price: number | null, observedAt: string, availability: PriceHistoryPoint['availability'] = 'in_stock'): PriceHistoryPoint =>
    ({ id, cardId: 1, collectionRunId: null, price: price === null ? null : price.toFixed(2), observedAt, availability })
  const metrics = priceMetrics([
    point(1, 100, '2026-10-01T01:00:00Z'), point(2, 140, '2026-10-01T12:00:00Z'),
    point(3, 80, '2026-10-02T01:00:00Z'), point(4, 50, '2026-10-03T01:00:00Z'),
    point(5, null, '2026-10-03T01:00:00Z', 'out_of_stock'),
  ])
  expect(metrics.latest?.id).toBe(5)
  expect(metrics.averagePrice).toBe('83.33333333333333333333')
  expect(metrics.minimumPrice).toBe('50.00')
  expect(metrics.baselineDays).toBe(3)
  expect(priceMetrics([point(1, 0, '2026-10-01T01:00:00Z')])).toMatchObject({ minimumPrice: "0.00", averagePrice: null, baselineDays: 0 })
  expect(priceMetrics([])).toMatchObject({ minimumPrice: null, averagePrice: null, baselineDays: 0 })
})
