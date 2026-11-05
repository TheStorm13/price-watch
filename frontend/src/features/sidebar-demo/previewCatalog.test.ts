import { describe, expect, it } from 'vitest'
import { catalogItems } from '../cards/catalogItems'
import { mockApi } from '../../api/mockApi'
import { buildPreviewCatalog, selectPreviewItems } from './previewCatalog'
import type { CatalogSnapshot, ProductGroup } from '../../types/domain'

async function groupedSnapshot(): Promise<CatalogSnapshot> {
  const original = await mockApi.getCatalog()
  const cards = original.cards.slice(0, 3).map((card, index) => ({ ...card, groupId: 42,
    title: `Товар ${index}`, externalId: `article-${index}`, tags: [['Первый'], ['Скрытый'], []][index],
    marketplace: (['ozon', 'wildberries', 'aliexpress'] as const)[index],
    currentAvailability: (['out_of_stock', 'in_stock', 'unknown'] as const)[index],
    currentPrice: ['100.00', '9.99', null][index] }))
  const group: ProductGroup = { id: 42, name: 'Сравнение', cardIds: cards.map(card => card.id),
    representativeCard: cards[0], representativeCardId: cards[0].id, currentPrice: cards[0].currentPrice,
    minimumPrice: cards[0].minimumPrice ?? null, savings: null, baselineDays: 30, isDeal: false, hasMemberDeals: false }
  return { cards, groups: [group], deals: original.deals.filter(deal => deal.card.id === cards[0].id) }
}

describe('sidebar preview catalog semantics', () => {
  it('finds nonrepresentative members and all tags; hides members that fail any condition', async () => {
    const snapshot = await groupedSnapshot()
    const model = buildPreviewCatalog(snapshot, new URLSearchParams('markets=wildberries&tags=Скрытый&stock=1&q=article-1&deals=non_deals'), new Map())
    expect(model.orderedItems).toHaveLength(1)
    expect(model.groupedCards.get(42)?.map(card => card.id)).toEqual([snapshot.cards[1].id])
    const item = model.orderedItems[0]
    expect(item.card?.id).toBe(snapshot.cards[1].id)
    expect(item.kind === 'group' && item.matchingCardCount).toBe(1)
    expect(item.kind === 'group' && item.group.cardIds).toHaveLength(3)
    expect(model.availableTags).toEqual(['Первый', 'Скрытый'])
    expect([model.matchingCount, model.totalCount]).toEqual([1, 3])
    expect(snapshot.groups[0].representativeCardId).toBe(snapshot.cards[0].id)
  })

  it('does not combine conditions across members and removes groups without matches', async () => {
    const snapshot = await groupedSnapshot()
    for (const query of ['markets=ozon&stock=1', 'markets=ozon&tags=Скрытый', 'q=missing']) {
      const model = buildPreviewCatalog(snapshot, new URLSearchParams(query), new Map())
      expect(model.orderedItems).toEqual([])
      expect(model.groupedCards.size).toBe(0)
      expect([model.matchingCount, model.totalCount]).toEqual([0, 3])
    }
    const untagged = buildPreviewCatalog(snapshot, new URLSearchParams('tags='), new Map())
    expect(untagged.groupedCards.get(42)?.map(card => card.id)).toEqual([snapshot.cards[2].id])
  })

  it('derives representative metrics from member sort, leaves unknown prices last and counts cards once', async () => {
    const snapshot = await groupedSnapshot()
    const deals = new Map(snapshot.deals.map(deal => [deal.card.id, deal]))
    for (const [sort, representativeId] of [['price-asc', snapshot.cards[1].id], ['price-desc', snapshot.cards[0].id], ['', snapshot.cards[0].id]] as const) {
      const model = buildPreviewCatalog(snapshot, new URLSearchParams({ sort }), deals)
      const item = model.orderedItems[0]
      expect(item.card?.id).toBe(representativeId)
      expect(item.kind === 'group' && item.group.currentPrice).toBe(item.card?.currentPrice)
      expect(item.kind === 'group' && item.group.minimumPrice).toBe(item.card?.minimumPrice ?? null)
      expect(item.kind === 'group' && item.group.isDeal).toBe(deals.has(representativeId))
      expect(model.groupedCards.get(42)?.at(-1)?.currentPrice).toBeNull()
      expect([model.matchingCount, model.totalCount]).toEqual([3, 3])
    }
    const ungrouped = buildPreviewCatalog({ ...snapshot, groups: [] }, new URLSearchParams(), deals)
    expect(ungrouped.orderedItems).toHaveLength(3)
    expect([ungrouped.matchingCount, ungrouped.totalCount]).toEqual([3, 3])
    const onlyDeals = buildPreviewCatalog(snapshot, new URLSearchParams('deals=deals'), deals)
    expect(onlyDeals.groupedCards.get(42)?.map(card => card.id)).toEqual([snapshot.cards[0].id])
  })

  it('defaults to all, matches untagged products on empty tags and preserves nonempty marketplaces', async () => {
    const snapshot = await mockApi.getCatalog()
    const cards = snapshot.cards.slice(0, 3).map((card, index) => ({ ...card, tags: index === 0 ? ['Дом'] : index === 1 ? ['Подарки'] : [] }))
    const items = catalogItems(cards, [], new Map())
    expect(selectPreviewItems(items, new URLSearchParams())).toHaveLength(3)
    expect(selectPreviewItems(items, new URLSearchParams('tags=')).map(item => item.id)).toEqual([3])
    expect(selectPreviewItems(items, new URLSearchParams('markets='))).toHaveLength(3)
    expect(selectPreviewItems(items, new URLSearchParams('markets=invalid'))).toHaveLength(3)
    expect(selectPreviewItems(items, new URLSearchParams('tags=Дом&tags=Подарки')).map(item => item.id).sort()).toEqual([1, 2])
    expect(selectPreviewItems(items, new URLSearchParams('markets=wildberries&markets=aliexpress'))).toHaveLength(0)
  })

  it('price order crosses deal priority, compares decimal values correctly and leaves null prices last', async () => {
    const snapshot = await mockApi.getCatalog()
    const cards = snapshot.cards.slice(0, 3).map((card, index) => ({ ...card, currentPrice: ['100.00', '9.99', null][index] }))
    const items = catalogItems(cards, [], new Map(snapshot.deals.map(deal => [deal.card.id, deal])))
    expect(selectPreviewItems(items, new URLSearchParams()).at(0)?.id).toBe(1)
    expect(selectPreviewItems(items, new URLSearchParams('sort=price-asc')).map(item => item.id)).toEqual([2, 1, 3])
    expect(selectPreviewItems(items, new URLSearchParams('sort=price-desc')).map(item => item.id)).toEqual([1, 2, 3])
  })

  it('searches marketplace articles rather than internal IDs, and stock excludes unknown availability', async () => {
    const snapshot = await mockApi.getCatalog()
    const cards = snapshot.cards.slice(0, 3).map((card, index) => ({ ...card, id: 123 + index, title: 'Товар', externalId: `9876${index}`,
      currentAvailability: (['in_stock', 'out_of_stock', null] as const)[index] }))
    const items = catalogItems(cards, [], new Map())
    expect(selectPreviewItems(items, new URLSearchParams('q=123'))).toHaveLength(0)
    expect(selectPreviewItems(items, new URLSearchParams('q=98761')).map(item => item.id)).toEqual([124])
    expect(selectPreviewItems(items, new URLSearchParams('stock=1')).map(item => item.id)).toEqual([123])
    expect(selectPreviewItems(items, new URLSearchParams())).toHaveLength(3)
  })
})
