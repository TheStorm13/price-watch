import { describe, expect, it } from 'vitest'
import type { Deal, MarketplaceCard, ProductGroup } from '../../types/domain'
import { cardItem, catalogItems, compareItems, matchesItem, parseSort, type DisplayItem, type Sort } from './catalogItems'

function card(id: number, overrides: Partial<MarketplaceCard> = {}): MarketplaceCard {
  return { id, title: `Card ${id}`, externalId: String(id), marketplace: 'ozon', currentPrice: 90,
    minimumPrice: 80, averagePrice: 100, dealsEnabled: true, currentAvailability: 'in_stock',
    createdAt: '2026-10-01T12:00:00Z', updatedAt: '2026-10-03T12:00:00Z', lastObservedAt: '2026-10-02T12:00:00Z',
    imageUrl: null, url: null, tags: ['representative'], ...overrides }
}
function group(representative: MarketplaceCard | null, overrides: Partial<ProductGroup> = {}): ProductGroup {
  return { id: 1, name: 'Group', tags: ['own'], cardIds: representative ? [representative.id, 2] : [],
    currentPrice: representative?.currentPrice ?? null, minimumPrice: representative?.minimumPrice ?? null,
    representativeCard: representative, representativeCardId: representative?.id ?? null,
    savings: null, baselineDays: 1, isDeal: false, hasMemberDeals: false, ...overrides }
}
const filters = { query: '', marketplace: 'all', status: 'all', tag: '', dealsOnly: false }
function groupItem(representative: MarketplaceCard | null, overrides: Partial<ProductGroup> = {}): DisplayItem {
  return catalogItems([], [group(representative, overrides)], new Map())[0]
}

describe('catalog objects', () => {
  it('builds groups before filtering and keeps members nested', () => {
    const representative = card(1, { groupId: 1 })
    const member = card(2, { groupId: 1, marketplace: 'wildberries', tags: ['other'], title: 'Hidden name' })
    const items = catalogItems([representative, member, card(3)], [group(representative)], new Map())
    expect(items.map((item) => [item.kind, item.id])).toEqual([['group', 1], ['card', 3]])
    const object = items[0]
    for (const patch of [{ marketplace: 'wildberries' }, { tag: 'other' }, { tag: 'own' }, { query: 'hidden name' }]) {
      expect(matchesItem(object, { ...filters, ...patch })).toBe(false)
    }
    for (const patch of [{ marketplace: 'ozon' }, { tag: 'representative' }, { query: 'group' }, { query: 'card 1' }]) {
      expect(matchesItem(object, { ...filters, ...patch })).toBe(true)
    }
    expect(object.card).toBe(representative)
  })

  it('uses identical filters for a card and its representing group', () => {
    for (const source of [card(1), card(1, { dealsEnabled: false, currentAvailability: 'out_of_stock' }),
      card(1, { currentPrice: null, currentAvailability: null, lastObservedAt: null })]) {
      const regular = cardItem(source, new Map())
      const grouped = groupItem(source)
      for (const patch of [{ status: 'in_stock' }, { status: 'out_of_stock' }, { status: 'no_data' },
        { status: 'deals_disabled' }, { dealsOnly: true }, { marketplace: 'wildberries' }, { tag: 'representative' }]) {
        expect(matchesItem(grouped, { ...filters, ...patch })).toBe(matchesItem(regular, { ...filters, ...patch }))
      }
    }
  })

  it('separates member priority from representative savings and deal filter', () => {
    const object = groupItem(card(1), { hasMemberDeals: true })
    expect(object.priority).toBe(true)
    expect(object.savings).toBeNull()
    expect(matchesItem(object, { ...filters, dealsOnly: true })).toBe(false)
    expect(compareItems(object, cardItem(card(2), new Map()), { key: 'price', direction: 'desc' })).toBeLessThan(0)
  })

  it('handles an empty group as an object without product data', () => {
    const object = groupItem(null)
    expect(matchesItem(object, filters)).toBe(true)
    expect(matchesItem(object, { ...filters, status: 'no_data' })).toBe(true)
    expect(matchesItem(object, { ...filters, marketplace: 'ozon' })).toBe(false)
    expect(matchesItem(object, { ...filters, dealsOnly: true })).toBe(false)
  })
})

describe('common sort', () => {
  const keys = ['title', 'marketplace', 'price', 'minimum', 'average', 'savings', 'availability', 'updated'] as const
  for (const key of keys) for (const direction of ['asc', 'desc'] as const) {
    const sort: Sort = { key, direction }
    it(`${key} ${direction} compares groups and cards by the same values`, () => {
      const low = card(1, { title: 'A', marketplace: 'aliexpress', currentPrice: 70, minimumPrice: 60,
        averagePrice: 80, currentAvailability: 'in_stock', updatedAt: '2026-10-01T12:00:00Z' })
      const high = card(2, { title: 'Z', marketplace: 'ozon', currentPrice: 100, minimumPrice: 90,
        averagePrice: 110, currentAvailability: 'unknown' })
      const deals = new Map<number, Deal>([[1, { card: low, averagePrice: 80, savings: 10, baselineDays: 1, lastCollectionRunId: null }],
        [2, { card: high, averagePrice: 110, savings: 20, baselineDays: 1, lastCollectionRunId: null }]])
      const left = groupItem(low, { name: 'A', savings: 10, isDeal: true })
      const right = cardItem(high, deals)
      expect(Math.sign(compareItems(left, right, sort))).toBe(direction === 'asc' ? -1 : 1)
      expect(Math.sign(compareItems(left, right, sort))).toBe(Math.sign(compareItems(cardItem(low, deals), right, sort)))
    })
  }

  for (const direction of ['asc', 'desc'] as const) it(`nulls stay last in ${direction}`, () => {
    const empty = groupItem(null)
    const present = cardItem(card(1), new Map())
    for (const key of keys.filter((key) => key !== 'title' && key !== 'savings')) {
      expect(compareItems(empty, present, { key, direction })).toBeGreaterThan(0)
    }
  })

  it('keeps deals first for every sort and direction', () => {
    const regular = cardItem(card(1), new Map())
    const deal = groupItem(card(2), { isDeal: true, savings: 10 })
    for (const key of keys) for (const direction of ['asc', 'desc'] as const) {
      expect(compareItems(deal, regular, { key, direction })).toBeLessThan(0)
    }
  })

  it('interleaves types and resolves equal IDs deterministically', () => {
    const items = [groupItem(card(1, { currentPrice: 90 }), { id: 1 }), cardItem(card(1, { currentPrice: 80 }), new Map()),
      groupItem(card(3, { currentPrice: 70 }), { id: 2 })]
    expect(items.toSorted((a, b) => compareItems(a, b, { key: 'price', direction: 'asc' }))
      .map((item) => [item.kind, item.card?.currentPrice])).toEqual([['group', 70], ['card', 80], ['group', 90]])
    const left = groupItem(card(1), { name: 'Card 1' })
    const right = cardItem(card(1), new Map())
    expect(compareItems(left, right, null)).not.toBe(0)
    expect(compareItems(left, right, null)).toBe(-compareItems(right, left, null))
  })
})

it('rejects malformed sort parameters', () => {
  for (const value of ['price-asc-', 'price-asc--ignored', 'unknown-asc', 'updated-asc', 'price']) expect(parseSort(value)).toBeNull()
  expect(parseSort('price-desc')).toEqual({ key: 'price', direction: 'desc' })
})
