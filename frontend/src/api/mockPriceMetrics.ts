import type { PriceHistoryPoint } from '../types/domain'
import { compareMoney, decimalParts, decimalText } from '../utils/money'

/** PostgreSQL timestamps retain microseconds even though Date parses milliseconds. */
function timestamp(value: string): bigint {
  const fraction = value.match(/\.(\d+)(?:Z|[+-]\d\d:\d\d)$/)?.[1] ?? ''
  return BigInt(Date.parse(value)) * 1000n + BigInt(fraction.padEnd(6, '0').slice(3, 6))
}

export function priceMetrics(points: PriceHistoryPoint[], asOf = Date.now()) {
  const end = BigInt(asOf) * 1000n
  const startDate = new Date(asOf)
  const month = startDate.getUTCMonth()
  startDate.setUTCFullYear(startDate.getUTCFullYear() - 2)
  if (startDate.getUTCMonth() !== month) startDate.setUTCDate(0) // Feb 29 → Feb 28
  const start = BigInt(startDate.getTime()) * 1000n
  const sorted = points.map(point => ({ point, at: timestamp(point.observedAt) }))
    .filter(({ at }) => at <= end)
    .sort((a, b) => a.at < b.at ? -1 : a.at > b.at ? 1 : a.point.id - b.point.id)
  const anchorIndex = sorted.findLastIndex(({ at }) => at < start)
  const window = sorted.slice(Math.max(0, anchorIndex))
  let minimumPrice: string | null = null, maximumPrice: string | null = null
  let total = 0n, durationSum = 0n, scale = 0, observationsCount = 0
  const days = new Set<string>()
  for (let index = 0; index < window.length; index++) {
    const { point, at } = window[index]
    const next = window[index + 1]?.at ?? end
    if (point.availability !== 'in_stock' || point.price === null || (at < start && next <= start)) continue
    if (minimumPrice === null || compareMoney(point.price, minimumPrice) < 0) minimumPrice = point.price
    if (maximumPrice === null || compareMoney(point.price, maximumPrice) > 0) maximumPrice = point.price
    if (at >= start) { observationsCount++; days.add(new Date(point.observedAt).toISOString().slice(0, 10)) }
    const duration = next - (at < start ? start : at)
    const [coefficient, priceScale] = decimalParts(point.price)
    if (priceScale > scale) { total *= 10n ** BigInt(priceScale - scale); scale = priceScale }
    total += coefficient * 10n ** BigInt(scale - priceScale) * duration
    durationSum += duration
  }
  let averagePrice: string | null = null
  if (durationSum > 0n) {
    // Match round(NUMERIC, 12): nearest, ties away from zero.
    const numerator = total * 10n ** 12n
    const denominator = durationSum * 10n ** BigInt(scale)
    const magnitude = numerator < 0n ? -numerator : numerator
    const rounded = magnitude / denominator + (magnitude % denominator * 2n >= denominator ? 1n : 0n)
    averagePrice = decimalText(numerator < 0n ? -rounded : rounded, 12)
  }
  return { minimumPrice, maximumPrice, averagePrice, baselineDays: days.size, observationsCount,
    windowStart: startDate.toISOString(), windowEnd: new Date(asOf).toISOString(), latest: sorted.at(-1)?.point }
}
