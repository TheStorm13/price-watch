/** Decimal strings are the wire/storage representation; never compare them lexically. */
export type DecimalString = string

export function decimalParts(value: DecimalString): [bigint, number] {
  if (typeof value !== 'string' || value.length > 128 || !/^-?\d+(?:\.\d+)?$/.test(value)) throw new Error('Некорректное денежное значение')
  const [whole, fraction = ''] = value.split('.')
  const sign = value.startsWith('-') ? -1n : 1n
  return [sign * BigInt(whole.replace('-', '') + fraction), fraction.length]
}

export function decimalText(coefficient: bigint, scale: number): DecimalString {
  const negative = coefficient < 0n
  const digits = (negative ? -coefficient : coefficient).toString().padStart(scale + 1, '0')
  return `${negative ? '-' : ''}${scale ? `${digits.slice(0, -scale)}.${digits.slice(-scale)}` : digits}`
}

export function compareMoney(first: DecimalString, second: DecimalString): number {
  const [a, as] = decimalParts(first)
  const [b, bs] = decimalParts(second)
  const scale = Math.max(as, bs)
  const difference = a * 10n ** BigInt(scale - as) - b * 10n ** BigInt(scale - bs)
  return difference < 0n ? -1 : difference > 0n ? 1 : 0
}

export function subtractMoney(first: DecimalString, second: DecimalString): DecimalString {
  const [a, as] = decimalParts(first), [b, bs] = decimalParts(second)
  const scale = Math.max(as, bs)
  return decimalText(a * 10n ** BigInt(scale - as) - b * 10n ** BigInt(scale - bs), scale)
}

export function midpointMoney(first: DecimalString, second: DecimalString): DecimalString {
  const [a, as] = decimalParts(first), [b, bs] = decimalParts(second)
  const scale = Math.max(as, bs)
  return decimalText((a * 10n ** BigInt(scale - as) + b * 10n ** BigInt(scale - bs)) * 5n, scale + 1)
}

export function priceText(value: DecimalString): DecimalString {
  const [coefficient, scale] = decimalParts(value)
  if (scale <= 2) return decimalText(coefficient * 10n ** BigInt(2 - scale), 2)
  const divisor = 10n ** BigInt(scale - 2)
  const magnitude = coefficient < 0n ? -coefficient : coefficient
  const rounded = magnitude / divisor + (magnitude % divisor * 2n >= divisor ? 1n : 0n)
  return decimalText(coefficient < 0n ? -rounded : rounded, 2)
}

export function formatMoney(value: DecimalString | null | undefined): string {
  if (value == null) return '—'
  // Round the original decimal once; wire values and calculations retain their precision.
  const [coefficient, scale] = decimalParts(value)
  const divisor = 10n ** BigInt(scale)
  const magnitude = coefficient < 0n ? -coefficient : coefficient
  const rounded = magnitude / divisor + (magnitude % divisor * 2n >= divisor ? 1n : 0n)
  const rubles = coefficient < 0n ? -rounded : rounded
  return `${rubles.toLocaleString('ru-RU')} ₽`
}
