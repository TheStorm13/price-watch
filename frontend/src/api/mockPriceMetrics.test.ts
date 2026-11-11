import { expect, it } from 'vitest'
import type { PriceHistoryPoint } from '../types/domain'
import { priceMetrics } from './mockPriceMetrics'

const now = Date.parse('2028-02-29T12:00:00Z')
const day = 86_400_000
const point = (id: number, price: string | null, at: number | string, availability: PriceHistoryPoint['availability'] = 'in_stock'): PriceHistoryPoint =>
  ({ id, cardId: 1, collectionRunId: null, price, observedAt: typeof at === 'string' ? at : new Date(at).toISOString(), availability })

it('weights durations, not price range or number of observations', () => {
  const points = [point(1, '1000.00', now - 30 * day), point(2, '3000.00', now - day)]
  const metrics = priceMetrics(points, now)
  expect(metrics).toMatchObject({ minimumPrice: '1000.00', maximumPrice: '3000.00', averagePrice: '1066.666666666667', baselineDays: 2 })
  expect(priceMetrics([...points, point(3, '1000.00', now - 20 * day)], now).averagePrice).toBe(metrics.averagePrice)
})

it('clips two calendar years, carries the preceding state, and ignores replaced old extrema and future points', () => {
  const metrics = priceMetrics([
    point(1, '1', '2025-01-01T00:00:00Z'), point(2, '100', '2026-01-01T00:00:00Z'),
    point(3, '5000', now + day),
  ], now)
  expect(metrics).toMatchObject({ minimumPrice: '100', maximumPrice: '100', averagePrice: '100.000000000000',
    baselineDays: 0, observationsCount: 0, windowStart: '2026-02-28T12:00:00.000Z' })
  expect(metrics.latest?.id).toBe(2)
  expect(priceMetrics([point(1, '1', '2023-01-01T00:00:00Z')], Date.parse('2026-11-11T15:00:00Z')).windowStart).toBe('2024-11-11T15:00:00.000Z')
})

it('does not carry a price through out-of-stock, unknown, or unpriced intervals', () => {
  const metrics = priceMetrics([
    point(1, '100', now - 6 * day), point(2, '999', now - 5 * day, 'out_of_stock'),
    point(3, '999', now - 4 * day, 'unknown'), point(4, null, now - 3 * day),
    point(5, '200', now - day), point(6, '0', now),
  ], now)
  expect(metrics).toMatchObject({ averagePrice: '150.000000000000', minimumPrice: '0', maximumPrice: '200', observationsCount: 3 })
})

it('uses ID for simultaneous states, retaining microsecond durations and exact decimal money', () => {
  const end = Date.parse('2026-10-01T00:00:00.001Z')
  const points = [point(1, '999', '2026-10-01T00:00:00.000000Z'),
    point(2, '100.00', '2026-10-01T00:00:00.000000Z'), point(3, '100.01', '2026-10-01T00:00:00.000500Z')]
  expect(priceMetrics(points, end).averagePrice).toBe('100.005000000000')
  expect(priceMetrics([point(1, '999999999999.98', '2026-10-01T00:00:00.000997Z'),
    point(2, '999999999999.99', '2026-10-01T00:00:00.000999Z')], end).averagePrice).toBe('999999999999.983333333333')
  expect(priceMetrics([point(1, '999999999999.99', end - 10), point(2, '999999999999.98', end - 5)], end).averagePrice).toBe('999999999999.985000000000')
})

it('returns null for empty or zero-duration history; a constant price averages to itself', () => {
  expect(priceMetrics([], now)).toMatchObject({ minimumPrice: null, averagePrice: null, baselineDays: 0 })
  expect(priceMetrics([point(1, '100', now)], now)).toMatchObject({ minimumPrice: '100', maximumPrice: '100', averagePrice: null })
  expect(priceMetrics([point(1, '0.00', now - 1)], now).averagePrice).toBe('0.000000000000')
  expect(priceMetrics([point(1, null, now - day, 'out_of_stock')], now).averagePrice).toBeNull()
  const start = Date.parse('2026-02-28T12:00:00Z')
  expect(priceMetrics([point(1, '1', start - 1), point(2, '100', start)], now)).toMatchObject({ minimumPrice: '100', averagePrice: '100.000000000000' })
})
