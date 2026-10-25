import { expect, it } from 'vitest'
import { compareMoney, decimalParts, formatMoney, midpointMoney, priceText, subtractMoney } from './money'

it('compares decimal magnitude and equivalent scales without float', () => {
  expect(compareMoney('9.90', '10.00')).toBe(-1)
  expect(compareMoney('199.9', '199.90')).toBe(0)
  expect(compareMoney('999999999999.99', '999999999999.98')).toBe(1)
  expect(compareMoney('1.00000000000000000001', '1')).toBe(1)
})
it('rounds half up with carry, preserves cents, and formats large values', () => {
  expect(priceText('199.995')).toBe('200.00')
  expect(priceText('0.005')).toBe('0.01')
  expect(priceText('-0.005')).toBe('-0.01')
  expect(formatMoney('999999999999.99')).toMatch(/999\s999\s999\s999,99\s₽/)
  expect(formatMoney('1.10')).toMatch(/1,10\s₽/)
  expect(formatMoney(null)).toBe('—')
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
