import { expect, it } from 'vitest'
import { compareMoney, decimalParts, formatMoney, midpointMoney, priceText, subtractMoney } from './money'

it('compares decimal magnitude and equivalent scales without float', () => {
  expect(compareMoney('9.90', '10.00')).toBe(-1)
  expect(compareMoney('199.9', '199.90')).toBe(0)
  expect(compareMoney('999999999999.99', '999999999999.98')).toBe(1)
  expect(compareMoney('1.00000000000000000001', '1')).toBe(1)
})
it('rounds wire values half up with carry and preserves cents', () => {
  expect(priceText('199.995')).toBe('200.00')
  expect(priceText('0.005')).toBe('0.01')
  expect(priceText('-0.005')).toBe('-0.01')
})
it.each([
  ['1234.49', '1 234 ₽'], ['1234.50', '1 235 ₽'],
  ['1.4999', '1 ₽'], ['1.5000', '2 ₽'], ['1.10', '1 ₽'],
  ['999999999999.99', '1 000 000 000 000 ₽'],
  ['9007199254740993.49', '9 007 199 254 740 993 ₽'],
  ['0.40', '0 ₽'], ['0.50', '1 ₽'], ['0', '0 ₽'], ['72990', '72 990 ₽'],
  ['-1.4999', '-1 ₽'], ['-1.50', '-2 ₽'], ['-0.40', '0 ₽'],
])('formats %s as whole rubles without float or double rounding', (value, expected) => {
  expect(formatMoney(value).replace(/\s/g, ' ')).toBe(expected)
})
it('preserves missing prices', () => {
  expect(formatMoney(null)).toBe('—')
  expect(formatMoney(undefined)).toBe('—')
})
it('computes the displayed range and midpoint without float', () => {
  expect(subtractMoney('0.30', '0.10')).toBe('0.20')
  expect(midpointMoney('0.01', '0.02')).toBe('0.015')
})
it('rejects invalid or unbounded decimal text', () => {
  for (const value of ['NaN', 'Infinity', '1e3', '', '1.2.3', '1'.repeat(129)]) {
    expect(() => decimalParts(value)).toThrow()
  }
})
