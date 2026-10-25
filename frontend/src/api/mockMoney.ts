/** Exact arithmetic confined to the database-free test fixture. */
import { decimalParts, decimalText } from '../utils/money'
export type Fraction = readonly [bigint, bigint]
function gcd(a: bigint, b: bigint): bigint {
  while (b) [a, b] = [b, a % b]
  return a < 0n ? -a : a
}
export function fraction(value: string): Fraction {
  const [coefficient, scale] = decimalParts(value)
  return [coefficient, 10n ** BigInt(scale)]
}
export function sumFractions(values: readonly Fraction[]): Fraction {
  return values.reduce<Fraction>(([a, b], [c, d]) => {
    const numerator = a * d + c * b, denominator = b * d
    const divisor = gcd(numerator, denominator)
    return [numerator / divisor, denominator / divisor]
  }, [0n, 1n])
}
export function meanFraction(values: readonly Fraction[]): Fraction {
  const [a, b] = sumFractions(values)
  return [a, b * BigInt(values.length)]
}
export function fractionText([a, b]: Fraction): string {
  const sign = a < 0n ? -1n : 1n
  const magnitude = (a < 0n ? -a : a) * 10n ** 20n
  const rounded = magnitude / b + (magnitude % b * 2n >= b ? 1n : 0n)
  return decimalText(sign * rounded, 20).replace(/\.?0+$/, '') || '0'
}
export const subtractMoney = (a: string, b: string) => {
  const [c, d] = fraction(b)
  return fractionText(sumFractions([fraction(a), [-c, d]]))
}
