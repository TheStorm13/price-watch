import { expect, it } from 'vitest'
import { mockAssessment } from './mockPurchase'
import type { PurchaseSettings } from '../types/domain'
const asOf = Date.parse('2026-11-12T00:00:00Z')
const settings: PurchaseSettings = { instanceId: 'test', smallRangeTolerance: '200', historicalSavingsShare: '70', targetNotificationsEnabled: false }
const input = { asOf, price: '860', availability: 'in_stock' as const, minimum: '800', maximum: '1000', average: '1000', target: '900', historyStartedAt: new Date(asOf - 31 * 86400000).toISOString() }
it('matches all OR criteria in domain order with exact decimal threshold', () => {
  expect(mockAssessment(input, settings)).toMatchObject({ isMatch: true, matches: ['small_range', 'target_price', 'historical_savings_share'], threshold: '860.00' })
  expect(mockAssessment({ ...input, price: '860.000000000001', target: null }, { ...settings, smallRangeTolerance: null }).matches).toEqual([])
})
it('requires strictly more than 30 days except for a target', () => {
  expect(mockAssessment({ ...input, historyStartedAt: new Date(asOf - 30 * 86400000).toISOString() }, settings).matches).toEqual(['target_price'])
  expect(mockAssessment({ ...input, historyStartedAt: null }, settings).historyEligible).toBe(false)
})
it('uses full range, allows constant price and zero tolerance, rejects undefined savings', () => {
  expect(mockAssessment({ ...input, price: '340', minimum: '315', maximum: '340', average: '320', target: null }, { ...settings, smallRangeTolerance: '50' }).matches).toEqual(['small_range'])
  expect(mockAssessment({ ...input, price: '800', minimum: '800', maximum: '800', average: '800', target: null }, { ...settings, smallRangeTolerance: '0' }).matches).toEqual(['small_range'])
  expect(mockAssessment({ ...input, availability: 'out_of_stock' }, settings).matches).toEqual([])
})
it('retains a subkopeck threshold for large prices', () => {
  const result = mockAssessment({ ...input, price: '999999999999.98', average: '999999999999.99', minimum: '999999999999.98', maximum: '999999999999.99', target: null }, settings)
  expect(result.threshold).toBe('999999999999.9830')
  expect(result.matches).toEqual(['small_range', 'historical_savings_share'])
})
