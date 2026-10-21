import type { PriceHistoryPoint } from '../types/domain'

// Demo uses saved observations, just as the PostgreSQL projections do.
export function priceMetrics(points: PriceHistoryPoint[]) {
  const sorted = points.toSorted((a, b) => Date.parse(b.observedAt) - Date.parse(a.observedAt) || b.id - a.id)
  const latest = sorted[0]
  const valid = sorted.filter((point) => point.availability === 'in_stock' && point.price !== null)
  const daily = new Map<string, { sum: number; count: number }>()
  for (const point of sorted.slice(1)) {
    if (point.availability !== 'in_stock' || point.price === null) continue
    const day = new Date(point.observedAt).toISOString().slice(0, 10)
    const aggregate = daily.get(day) ?? { sum: 0, count: 0 }
    aggregate.sum += point.price
    aggregate.count += 1
    daily.set(day, aggregate)
  }
  const dailyMeans = [...daily.values()].map(({ sum, count }) => sum / count)
  return { latest, minimumPrice: valid.length ? Math.min(...valid.map((point) => point.price!)) : null,
    averagePrice: dailyMeans.length ? dailyMeans.reduce((sum, price) => sum + price, 0) / dailyMeans.length : null,
    baselineDays: daily.size }
}
