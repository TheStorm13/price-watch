import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from './mockApi'

afterEach(() => vi.restoreAllMocks())

describe('mock deal list', () => {
  it('does not wait seven days after the card was created', async () => {
    const card = await mockApi.getCard(1)
    const clock = vi.spyOn(Date, 'now').mockReturnValue(Date.parse(card.lastObservedAt!))
    try {
      expect(((await mockApi.getCatalog()).deals).map((deal) => deal.card.id)).toContain(card.id)
    } finally {
      clock.mockRestore()
    }
  })
})

it('projects every group field from one cheapest member and switches as prices change', async () => {
  vi.resetModules()
  const { mockApi: api } = await import('./mockApi')
  vi.spyOn(Date, 'now').mockReturnValue(Date.parse('2026-10-03T12:00:00Z'))
  const createdAt = '2026-10-01T12:00:00Z'
  const imported = (externalId: string, marketplace: 'ozon' | 'wildberries', prices: number[]) => ({
    externalId, marketplace, title: `Fixture ${externalId}`, url: null, tags: [externalId],
    createdAt, dealsEnabled: true, primaryExternalId: marketplace === 'wildberries' ? `${externalId}:1` : externalId, variants: [{externalId: marketplace === 'wildberries' ? `${externalId}:1` : externalId, url: null, history: prices.map((price, index) => ({
      price: String(price), availability: 'in_stock' as const, observedAt: `2026-10-0${index + 1}T12:00:00Z`,
    })), }],
  })
  await api.importCards({ version: 3, cards: [imported('901', 'ozon', [80, 90]), imported('902', 'wildberries', [60, 240, 120])],
    groups: [{ name: 'Fixture', cards: [{ marketplace: 'ozon', externalId: '901' }, { marketplace: 'wildberries', externalId: '902' }] }] })
  let group = ((await api.getCatalog()).groups)[0]
  expect(group.representativeCard).toMatchObject({ externalId: '901', currentPrice: "90.00", minimumPrice: "80.00", averagePrice: "85.000000000000" })
  expect(group).toMatchObject({ currentPrice: "90.00", minimumPrice: "80.00", savings: null, isDeal: false, hasMemberDeals: true, baselineDays: 2 })
  expect(group.representativeCard).toEqual(((await api.getCatalog()).cards).find((card) => card.externalId === '901'))
  vi.spyOn(Date, 'now').mockReturnValue(Date.parse('2026-10-04T12:00:00Z'))
  await api.importCards({ version: 3, cards: [imported('902', 'wildberries', [60, 240, 120, 50])] })
  group = ((await api.getCatalog()).groups)[0]
  expect(group.representativeCard).toMatchObject({ externalId: '902', currentPrice: "50.00", minimumPrice: "50.00", marketplace: 'wildberries' })
  expect(group).toMatchObject({ isDeal: true, hasMemberDeals: true, savings: "90.000000000000", baselineDays: 4 })
  await api.updateCard(group.representativeCardId!, { dealsEnabled: false })
  group = ((await api.getCatalog()).groups)[0]
  expect(group).toMatchObject({ isDeal: false, savings: null, hasMemberDeals: false })
  const empty = await api.createGroup({ name: 'Empty', cardIds: [] })
  expect(empty).toMatchObject({ representativeCard: null, currentPrice: null, minimumPrice: null, baselineDays: 0, isDeal: false })
  const unpriced = await api.createCard({ marketplace: 'ozon', externalId: '903' })
  const noData = await api.createGroup({ name: 'No data', cardIds: [unpriced.id] })
  expect(noData.representativeCardId).toBe(unpriced.id)
  expect(noData.representativeCard?.lastObservedAt).toBeNull()
})

it('projects every displayed field from the primary variant and edits it independently', async () => {
  vi.resetModules()
  const { mockApi: api } = await import('./mockApi')
  await api.importCards({ version: 3, cards: [{ marketplace: 'wildberries', externalId: '77777', title: 'Первый', url: null,
    createdAt: '2026-10-01T12:00:00Z', dealsEnabled: true, primaryExternalId: '77777:1', variants: [1,2].map((id) => ({
      externalId: `77777:${id}`, title: `Размер ${id}`, productTitle: id === 1 ? 'Первый' : 'Второй', imageUrl: id === 1 ? 'https://img.test/one.webp' : null,
      url: `https://www.wildberries.ru/catalog/77777/detail.aspx?size=${id}`, options: { Размер: String(id) },
      history: [{ price: `${id}0.00`, availability: 'in_stock', observedAt: '2026-10-01T12:00:00Z' }],
    })) }] })
  const card = (await api.getCatalog()).cards.find((c) => c.externalId === '77777')!
  const variants = await api.getVariants(card.id)
  expect(card.imageUrl).toBe('https://img.test/one.webp')
  const switched = await api.updateCard(card.id, { primaryVariantId: variants[1].id })
  expect(switched).toMatchObject({ title: 'Второй', imageUrl: null, options: { Размер: '2' }, currentPrice: '20.00' })
  await api.updateCard(card.id, { title: 'Мой второй' })
  const first = await api.updateCard(card.id, { primaryVariantId: variants[0].id })
  expect(first).toMatchObject({ title: 'Первый', imageUrl: 'https://img.test/one.webp', currentPrice: '10.00' })
})
