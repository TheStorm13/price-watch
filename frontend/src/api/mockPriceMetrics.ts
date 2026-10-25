import type { PriceHistoryPoint } from '../types/domain'
import { compareMoney } from '../utils/money'
import { fraction, fractionText, meanFraction, type Fraction } from './mockMoney'

function metrics(points: PriceHistoryPoint[]) {
  const valid = points.filter((point) => point.availability === 'in_stock' && point.price !== null)
  const daily = new Map<string, Fraction[]>()
  for (const point of valid) {
    const day = new Date(point.observedAt).toISOString().slice(0, 10)
    const values = daily.get(day) ?? []
    values.push(fraction(point.price!))
    daily.set(day, values)
  }
  const prices = valid.map((point) => point.price!).sort(compareMoney)
  return {
    minimumPrice: prices[0] ?? null, maximumPrice: prices.at(-1) ?? null,
    averagePrice: daily.size ? fractionText(meanFraction([...daily.values()].map(meanFraction))) : null,
    baselineDays: daily.size, observationsCount: valid.length,
  }
}

// Prior daily means exclude the latest observation, matching the deal baseline.
export function priceMetrics(points: PriceHistoryPoint[]) {
  const sorted = points.toSorted((a, b) => Date.parse(b.observedAt) - Date.parse(a.observedAt) || b.id - a.id)
  return { ...metrics(sorted.slice(1)), minimumPrice: metrics(sorted).minimumPrice, latest: sorted[0] }
}
export const historyMetrics = metrics
