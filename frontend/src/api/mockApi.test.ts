import { describe, expect, it, vi } from 'vitest'
import { mockApi } from './mockApi'

describe('mock deal list', () => {
  it('does not wait seven days after the card was created', async () => {
    const card = await mockApi.getCard(1)
    const clock = vi.spyOn(Date, 'now').mockReturnValue(Date.parse(card.createdAt) + 6 * 86_400_000)
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
  const createdAt = '2026-10-01T12:00:00Z'
  const imported = (externalId: string, marketplace: 'ozon' | 'wildberries', prices: number[]) => ({
    externalId, marketplace, title: `Fixture ${externalId}`, url: null, tags: [externalId],
    createdAt, dealsEnabled: true, history: prices.map((price, index) => ({
      price: String(price), availability: 'in_stock' as const, observedAt: `2026-10-0${index + 1}T12:00:00Z`,
    })),
  })
  await api.importCards({ version: 2, cards: [imported('901', 'ozon', [80, 90]), imported('902', 'wildberries', [60, 240, 120])],
    groups: [{ name: 'Fixture', cards: [{ marketplace: 'ozon', externalId: '901' }, { marketplace: 'wildberries', externalId: '902' }] }] })
  let group = ((await api.getCatalog()).groups)[0]
  expect(group.representativeCard).toMatchObject({ externalId: '901', currentPrice: 90, minimumPrice: 80, averagePrice: 80 })
  expect(group).toMatchObject({ currentPrice: 90, minimumPrice: 80, savings: null, isDeal: false, hasMemberDeals: true, baselineDays: 1 })
  expect(group.representativeCard).toEqual(((await api.getCatalog()).cards).find((card) => card.externalId === '901'))
  await api.importCards({ version: 2, cards: [imported('902', 'wildberries', [60, 240, 120, 50])] })
  group = ((await api.getCatalog()).groups)[0]
  expect(group.representativeCard).toMatchObject({ externalId: '902', currentPrice: 50, minimumPrice: 50, marketplace: 'wildberries' })
  expect(group).toMatchObject({ isDeal: true, hasMemberDeals: true, savings: 90, baselineDays: 3 })
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
