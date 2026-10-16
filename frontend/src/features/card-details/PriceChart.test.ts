import { describe, expect, it } from 'vitest'
import type { PriceHistoryPoint } from '../../types/domain'
import { priceDomain, turningPointIndices } from './PriceChart'

const history = (prices: Array<number | null>): PriceHistoryPoint[] => prices.map((price, index) => ({
  id: index + 1, cardId: 1, collectionRunId: 1, price,
  availability: price === null ? 'out_of_stock' : 'in_stock',
  observedAt: new Date(2026, 0, index + 1).toISOString(),
}))

describe('price chart scale and labels', () => {
  it('uses visible prices with ten percent padding and preserves zero', () => {
    expect(priceDomain(history([100, 120, null]))).toEqual([98, 122])
    expect(priceDomain(history([0, 10]))).toEqual([0, 11])
    expect(priceDomain(history([100, 100]))).toEqual([90, 110])
    expect(priceDomain(history([null]))).toEqual([0, 1])
  })

  it('labels important turns without filling a flat line with labels', () => {
    expect([...turningPointIndices(history([100, 80, 110, 90, 120]))]).toEqual([1, 4])
    expect(turningPointIndices(history([100, 100, 100])).size).toBe(0)
  })
})
