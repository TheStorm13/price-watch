import { describe, expect, it } from 'vitest'
import { catalogItems } from '../cards/catalogItems'
import { mockApi } from '../../api/mockApi'
import { selectPreviewItems } from './previewCatalog'

describe('sidebar preview catalog semantics', () => {
  it('defaults to all including untagged products, handles empty selection and OR tags', async () => {
    const snapshot = await mockApi.getCatalog()
    const cards = snapshot.cards.slice(0, 3).map((card, index) => ({ ...card, tags: index === 0 ? ['Дом'] : index === 1 ? ['Подарки'] : [] }))
    const items = catalogItems(cards, [], new Map())
    expect(selectPreviewItems(items, new URLSearchParams())).toHaveLength(3)
    expect(selectPreviewItems(items, new URLSearchParams('tags='))).toHaveLength(0)
    expect(selectPreviewItems(items, new URLSearchParams('markets='))).toHaveLength(0)
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
