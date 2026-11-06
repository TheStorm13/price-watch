import type { CatalogSnapshot, TrackedCardView } from '../types/domain'

/** Seeded, mock-only data. The default shape retains the E2E names and order. */
export function performanceData(count: number, shape: string, varied = false, now = '2026-01-01T00:00:00.000Z'): CatalogSnapshot {
  const cards: TrackedCardView[] = Array.from({ length: count }, (_, i) => ({
    id: 10000 + i, primaryVariantId: 10000 + i, externalId: String(10000 + i), marketplace: 'ozon', title: `Тестовый товар ${String(i).padStart(5, '0')}`,
    groupId: shape === 'group' ? 1 : shape === 'mixed' && i % 2 === 0 ? Math.floor(i / 10) + 1 : null,
    tags: [], url: null, imageUrl: null, dealsEnabled: true, currentPrice: '100.00', minimumPrice: '90.00',
    averagePrice: '110.00', currentAvailability: 'in_stock', lastObservedAt: now, lastCollectedAt: now, createdAt: now, updatedAt: now,
  }))
  if (varied) {
    let seed = 42
    const random = () => ((seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) / 4294967296)
    for (const [i, card] of cards.entries()) {
      card.title = `${['Тестовый товар', 'тестовый Товар', 'Тестовый адаптер', 'Тестовый кабель'][i % 4]} ${Math.floor(random() * 100000)}`
      card.marketplace = (['ozon', 'wildberries', 'aliexpress', 'yandex-market'] as const)[i % 4]
      card.currentPrice = i % 17 === 0 ? null : (Math.floor(random() * 1000000) / 100).toFixed(2)
      card.minimumPrice = i % 19 === 0 ? null : (Math.floor(random() * 1000000) / 100).toFixed(2)
      card.averagePrice = i % 23 === 0 ? null : (Math.floor(random() * 1000000) / 100).toFixed(2)
      card.currentAvailability = (['in_stock', 'out_of_stock', 'unknown'] as const)[i % 3]
      card.tags = i % 5 === 0 ? [] : [`Тег ${i % 20}`]
      card.dealsEnabled = i % 7 !== 0
    }
  }
  const members = new Map<number, TrackedCardView[]>()
  for (const card of cards) if (card.groupId != null) {
    const group = members.get(card.groupId) ?? []
    group.push(card); members.set(card.groupId, group)
  }
  const snapshot: CatalogSnapshot = { cards, deals: [], groups: [...members].map(([id, group]) => ({
    id, name: `Тестовая группа ${id}`, tags: [], cardIds: group.map(card => card.id),
    representativeCardId: group[0].id, representativeCard: group[0], currentPrice: '100.00', minimumPrice: '90.00',
    savings: null, baselineDays: 30, isDeal: false, hasMemberDeals: false,
  })) }
  if (varied) snapshot.deals = cards.filter((card, i) => i % 3 === 0 && card.dealsEnabled).map(card => ({
    card, averagePrice: card.averagePrice ?? '110.00', savings: '10.00', baselineDays: 30, lastCollectionRunId: null,
  }))
  return snapshot
}
