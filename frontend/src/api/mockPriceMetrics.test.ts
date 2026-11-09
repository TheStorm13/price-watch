import { expect, it } from 'vitest'
import type { PriceHistoryPoint } from '../types/domain'
import { historyMetrics, priceMetrics } from './mockPriceMetrics'

it('uses the full price range, latest ordering and availability like the server', () => {
  const point = (id: number, price: number | null, observedAt: string, availability: PriceHistoryPoint['availability'] = 'in_stock'): PriceHistoryPoint =>
    ({ id, cardId: 1, collectionRunId: null, price: price === null ? null : price.toFixed(2), observedAt, availability })
  const metrics = priceMetrics([
    point(1, 100, '2026-10-01T01:00:00Z'), point(2, 140, '2026-10-01T12:00:00Z'),
    point(3, 80, '2026-10-02T01:00:00Z'), point(4, 50, '2026-10-03T01:00:00Z'),
    point(5, null, '2026-10-03T01:00:00Z', 'out_of_stock'),
  ])
  expect(metrics.latest?.id).toBe(5)
  expect(metrics.averagePrice).toBe('95.000')
  expect(metrics.minimumPrice).toBe('50.00')
  expect(metrics.baselineDays).toBe(3)
  expect(priceMetrics([point(1, 0, '2026-10-01T01:00:00Z')])).toMatchObject({ minimumPrice: "0.00", averagePrice: "0.000", baselineDays: 1 })
  expect(priceMetrics([])).toMatchObject({ minimumPrice: null, averagePrice: null, baselineDays: 0 })
})

const point = (id: number, price: string | null, availability: PriceHistoryPoint['availability'] = 'in_stock'): PriceHistoryPoint =>
  ({ id, cardId: 1, collectionRunId: null, price, availability, observedAt: `2026-10-01T0${id}:00:00Z` })

it('includes the latest price and ignores observation frequency in both metric views', () => {
  for (const metrics of [priceMetrics, historyMetrics]) {
    expect(metrics([point(1, '100'), point(2, '120')]).averagePrice).toBe('110.0')
    expect(metrics([point(1, '100'), point(2, '100'), point(3, '160')]).averagePrice).toBe('130.0')
    expect(metrics([point(1, '100.00'), point(2, '100.01')]).averagePrice).toBe('100.005')
    expect(metrics([point(1, '999', 'unknown'), point(2, null, 'out_of_stock')])).toMatchObject({ averagePrice: null, baselineDays: 0 })
  }
})
