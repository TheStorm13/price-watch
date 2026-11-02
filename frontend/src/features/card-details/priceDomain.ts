import type { PriceHistoryPoint } from '../../types/domain'

export function priceDomain(history: PriceHistoryPoint[]): [number, number] {
  const prices = history.flatMap((point) => point.price === null ? [] : [Number(point.price)])
  if (prices.length === 0) return [0, 1]
  let minimum = Infinity, maximum = -Infinity
  for (const price of prices) { minimum = Math.min(minimum, price); maximum = Math.max(maximum, price) }
  const padding = maximum === minimum ? Math.max(maximum * 0.1, 1) : (maximum - minimum) * 0.1
  return [Math.max(0, minimum - padding), maximum + padding]
}
