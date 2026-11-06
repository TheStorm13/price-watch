import { describe, expect, it } from 'vitest'
import { cardItem } from './catalogItems'
import { mockApi } from '../../api/mockApi'
import { buildCatalog, selectCatalogItems, prepareCatalog, catalogTags, catalogComparator } from './catalogModel'
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

describe('catalog filtering and grouping', () => {
  it('finds nonrepresentative members and all tags; hides members that fail any condition', async () => {
    const snapshot = await groupedSnapshot()
    const model = buildCatalog(prepareCatalog(snapshot, new Map()), new URLSearchParams('markets=wildberries&tags=Скрытый&stock=1&q=article-1&deals=non_deals'))
    expect(model.orderedItems).toHaveLength(1)
    expect(model.groupedCards.get(42)?.map(card => card.id)).toEqual([snapshot.cards[1].id])
    const item = model.orderedItems[0]
    expect(item.card?.id).toBe(snapshot.cards[1].id)
    expect(item.kind === 'group' && item.matchingCardCount).toBe(1)
    expect(item.kind === 'group' && item.group.cardIds).toHaveLength(3)
    expect(catalogTags(snapshot.cards)).toEqual(['Первый', 'Скрытый'])
    expect([model.matchingCount, model.totalCount]).toEqual([1, 3])
    expect(snapshot.groups[0].representativeCardId).toBe(snapshot.cards[0].id)
  })

  it('does not combine conditions across members and removes groups without matches', async () => {
    const snapshot = await groupedSnapshot()
    for (const query of ['markets=ozon&stock=1', 'markets=ozon&tags=Скрытый', 'q=missing']) {
      const model = buildCatalog(prepareCatalog(snapshot, new Map()), new URLSearchParams(query))
      expect(model.orderedItems).toEqual([])
      expect(model.groupedCards.size).toBe(0)
      expect([model.matchingCount, model.totalCount]).toEqual([0, 3])
    }
    const untagged = buildCatalog(prepareCatalog(snapshot, new Map()), new URLSearchParams('tags='))
    expect(untagged.groupedCards.get(42)?.map(card => card.id)).toEqual([snapshot.cards[2].id])
  })

  it('derives representative metrics from member sort, leaves unknown prices last and counts cards once', async () => {
    const snapshot = await groupedSnapshot()
    const deals = new Map(snapshot.deals.map(deal => [deal.card.id, deal]))
    for (const [sort, representativeId] of [['price-asc', snapshot.cards[1].id], ['price-desc', snapshot.cards[0].id], ['', snapshot.cards[0].id]] as const) {
      const model = buildCatalog(prepareCatalog(snapshot, deals), new URLSearchParams({ sort }))
      const item = model.orderedItems[0]
      expect(item.card?.id).toBe(representativeId)
      expect(item.kind === 'group' && item.group.currentPrice).toBe(item.card?.currentPrice)
      expect(item.kind === 'group' && item.group.minimumPrice).toBe(item.card?.minimumPrice ?? null)
      expect(item.kind === 'group' && item.group.isDeal).toBe(deals.has(representativeId))
      expect(model.groupedCards.get(42)?.at(-1)?.currentPrice).toBeNull()
      expect([model.matchingCount, model.totalCount]).toEqual([3, 3])
    }
    const ungrouped = buildCatalog(prepareCatalog({ ...snapshot, groups: [] }, deals), new URLSearchParams())
    expect(ungrouped.orderedItems).toHaveLength(3)
    expect([ungrouped.matchingCount, ungrouped.totalCount]).toEqual([3, 3])
    const onlyDeals = buildCatalog(prepareCatalog(snapshot, deals), new URLSearchParams('deals=deals'))
    expect(onlyDeals.groupedCards.get(42)?.map(card => card.id)).toEqual([snapshot.cards[0].id])
  })

  it('defaults to all, matches untagged products on empty tags and preserves nonempty marketplaces', async () => {
    const snapshot = await mockApi.getCatalog()
    const cards = snapshot.cards.slice(0, 3).map((card, index) => ({ ...card, tags: index === 0 ? ['Дом'] : index === 1 ? ['Подарки'] : [] }))
    const items = cards.map(card => cardItem(card, new Map()))
    expect(selectCatalogItems(items, new URLSearchParams())).toHaveLength(3)
    expect(selectCatalogItems(items, new URLSearchParams('tags=')).map(item => item.id)).toEqual([3])
    expect(selectCatalogItems(items, new URLSearchParams('markets='))).toHaveLength(3)
    expect(selectCatalogItems(items, new URLSearchParams('markets=invalid'))).toHaveLength(3)
    expect(selectCatalogItems(items, new URLSearchParams('tags=Дом&tags=Подарки')).map(item => item.id).sort()).toEqual([1, 2])
    expect(selectCatalogItems(items, new URLSearchParams('markets=wildberries&markets=aliexpress'))).toHaveLength(0)
  })

  it('price order crosses deal priority, compares decimal values correctly and leaves null prices last', async () => {
    const snapshot = await mockApi.getCatalog()
    const cards = snapshot.cards.slice(0, 3).map((card, index) => ({ ...card, currentPrice: ['100.00', '9.99', null][index] }))
    const items = cards.map(card => cardItem(card, new Map(snapshot.deals.map(deal => [deal.card.id, deal]))))
    expect(selectCatalogItems(items, new URLSearchParams()).at(0)?.id).toBe(1)
    expect(selectCatalogItems(items, new URLSearchParams('sort=price-asc')).map(item => item.id)).toEqual([2, 1, 3])
    expect(selectCatalogItems(items, new URLSearchParams('sort=price-desc')).map(item => item.id)).toEqual([1, 2, 3])
  })

  it('sorts all column values in both directions with missing money last', async () => {
    const snapshot = await mockApi.getCatalog()
    const cards = snapshot.cards.slice(0, 3).map((card, index) => ({ ...card,
      title: ['Б', 'А', 'В'][index], minimumPrice: ['100.00', '9.99', null][index],
      averagePrice: ['100.00', '9.99', null][index],
      marketplace: (['ozon', 'aliexpress', 'wildberries'] as const)[index],
      currentAvailability: (['out_of_stock', 'in_stock', 'unknown'] as const)[index] }))
    const items = cards.map(card => cardItem(card, new Map()))
    for (const key of ['title', 'minimum', 'average', 'marketplace', 'availability']) {
      expect(selectCatalogItems(items, new URLSearchParams(`sort=${key}-asc`)).map(item => item.id)).toEqual([2, 1, 3])
      const descending = key === 'minimum' || key === 'average' ? [1, 2, 3] : key === 'availability' ? [1, 3, 2] : [3, 1, 2]
      expect(selectCatalogItems(items, new URLSearchParams(`sort=${key}-desc`)).map(item => item.id)).toEqual(descending)
    }
    const savings = items.map((item, index) => ({ ...item, savings: ['100.00', '9.99', null][index] }))
    expect(selectCatalogItems(savings, new URLSearchParams('sort=savings-asc')).map(item => item.id)).toEqual([2, 1, 3])
    expect(selectCatalogItems(savings, new URLSearchParams('sort=savings-desc')).map(item => item.id)).toEqual([1, 2, 3])
  })

  it('searches marketplace articles rather than internal IDs, and stock excludes unknown availability', async () => {
    const snapshot = await mockApi.getCatalog()
    const cards = snapshot.cards.slice(0, 3).map((card, index) => ({ ...card, id: 123 + index, title: 'Товар', externalId: `9876${index}`,
      currentAvailability: (['in_stock', 'out_of_stock', null] as const)[index] }))
    const items = cards.map(card => cardItem(card, new Map()))
    expect(selectCatalogItems(items, new URLSearchParams('q=123'))).toHaveLength(0)
    expect(selectCatalogItems(items, new URLSearchParams('q=98761')).map(item => item.id)).toEqual([124])
    expect(selectCatalogItems(items, new URLSearchParams('stock=1')).map(item => item.id)).toEqual([123])
    expect(selectCatalogItems(items, new URLSearchParams())).toHaveLength(3)
  })
})

it('orders numeric Cyrillic names and retains ID ties, group names and snapshot data', async () => {
 const snapshot = await groupedSnapshot()
 const cards = snapshot.cards.map((card,i)=>({...card,title:['Товар 10','товар 2','ТОВАР 2'][i],groupId:i===0?42:null}))
 const original={...snapshot,cards,groups:[{...snapshot.groups[0],name:'Адаптер 1'}]}
 const frozen=JSON.stringify(original)
 const prepared=prepareCatalog(original,new Map())
 for(const direction of ['asc','desc']) {
  const model=buildCatalog(prepared,new URLSearchParams({sort:`title-${direction}`}))
  expect(model.orderedItems.map(item=>item.id)).toEqual(direction==='asc'?[42,cards[1].id,cards[2].id]:[cards[1].id,cards[2].id,42])
 }
 expect(JSON.stringify(original)).toBe(frozen)
 const items=cards.map(card=>cardItem(card,new Map()))
 expect(items.toSorted(catalogComparator('title-asc')).map(item=>item.id)).toEqual([cards[1].id,cards[2].id,cards[0].id])
})
