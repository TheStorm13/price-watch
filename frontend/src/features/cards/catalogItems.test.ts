import { describe, expect, it } from 'vitest'
import type { TrackedCardView } from '../../types/domain'
import { cardItem, compareItems } from './catalogItems'

function card(id: number, overrides: Partial<TrackedCardView> = {}): TrackedCardView {
  return { id, title: `Card ${id}`, externalId: String(id), marketplace: 'ozon', currentPrice: "90.00",
    minimumPrice: "80.00", averagePrice: "100.00", dealsEnabled: true, currentAvailability: 'in_stock',
    createdAt: '2026-10-01T12:00:00Z', updatedAt: '2026-10-03T12:00:00Z', lastObservedAt: '2026-10-02T12:00:00Z',
    imageUrl: null, url: null, tags: ['representative'], ...overrides }
}
describe('default catalog ordering and savings', () => {
  it('puts participation before savings and savings before availability or deal eligibility', () => {
    const regular = { ...cardItem(card(1), new Map()), savings: '10.01' }
    const eligible = { ...cardItem(card(2), new Map()), priority: true, savings: '10.00' }
    const disabled = { ...cardItem(card(3, { dealsEnabled: false }), new Map()), savings: '100.00' }
    const missing = cardItem(card(4, { currentAvailability: null, currentPrice: null }), new Map())
    const unavailable = { ...cardItem(card(5, { currentAvailability: 'out_of_stock' }), new Map()), savings: '20.00' }
    const items = [disabled, missing, eligible, regular, unavailable]
    expect(items.toSorted((a, b) => compareItems(a, b)).map(item => item.id)).toEqual([5, 1, 2, 4, 3])
    expect(items.toSorted((a, b) => compareItems(a, b, false)).map(item => item.id)).toEqual([3, 5, 1, 2, 4])
  })

  it('shows disabled savings without marking the card as an eligible deal', () => {
    const item = cardItem(card(1, { dealsEnabled: false, averagePrice: '100.25', currentPrice: '70.10' }), new Map())
    expect(item.savings).toBe('30.15')
    expect(item.priority).toBe(false)
  })

  it('keeps unavailable, missing and nonpositive savings out of display', () => {
    for (const patch of [{ averagePrice: null }, { currentPrice: null }, { currentAvailability: 'out_of_stock' as const },
      { currentPrice: '100.00' }, { currentPrice: '110.00' }]) {
      expect(cardItem(card(1, { dealsEnabled: false, ...patch }), new Map()).savings).toBeNull()
    }
  })

  it('compares exact decimal savings and resolves ties deterministically', () => {
    const a = cardItem(card(1, { currentPrice: '1.02', averagePrice: '2.00' }), new Map())
    const b = cardItem(card(2, { currentPrice: '1.01', averagePrice: '2.00' }), new Map())
    expect([a,b].toSorted(compareItems).map(item => item.id)).toEqual([2,1])
    expect(compareItems(a, { ...a, id: 3 })).toBeLessThan(0)
  })
})
