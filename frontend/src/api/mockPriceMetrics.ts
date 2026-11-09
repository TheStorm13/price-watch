import type { PriceHistoryPoint } from '../types/domain'
import { compareMoney, midpointMoney } from '../utils/money'

function metrics(points: PriceHistoryPoint[]) {
  const valid = points.filter((point) => point.availability === 'in_stock' && point.price !== null)
  const days = new Set(valid.map((point) => new Date(point.observedAt).toISOString().slice(0, 10)))
  const prices = valid.map((point) => point.price!).sort(compareMoney)
  const minimumPrice = prices[0] ?? null
  const maximumPrice = prices.at(-1) ?? null
  return {
    minimumPrice, maximumPrice,
    averagePrice: minimumPrice !== null && maximumPrice !== null ? midpointMoney(minimumPrice, maximumPrice) : null,
    baselineDays: days.size, observationsCount: valid.length,
  }
}

export function priceMetrics(points: PriceHistoryPoint[]) {
  const sorted = points.toSorted((a, b) => Date.parse(b.observedAt) - Date.parse(a.observedAt) || b.id - a.id)
  return { ...metrics(sorted), latest: sorted[0] }
}
export const historyMetrics = metrics
