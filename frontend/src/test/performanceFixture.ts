// Loaded only in the mock build, never in the desktop runtime.
import { api } from '../api/client'
import { queryClient } from '../app/providers'
import type { CatalogSnapshot, TrackedCardView } from '../types/domain'

export function installPerformanceFixture() {
  const params = new URLSearchParams(location.search)
  const count = Number(params.get('perf'))
  if (![100, 1000, 5000].includes(count)) return
  const shape = params.get('shape') ?? 'plain'
  const now = new Date().toISOString()
  const cards: TrackedCardView[] = Array.from({ length: count }, (_, i) => ({
    id: 10000 + i, externalId: String(10000 + i), marketplace: 'ozon', title: `Тестовый товар ${String(i).padStart(5, '0')}`,
    groupId: shape === 'group' ? 1 : shape === 'mixed' && i % 2 === 0 ? Math.floor(i / 10) + 1 : null,
    tags: [], url: null, imageUrl: null, dealsEnabled: true, currentPrice: '100.00', minimumPrice: '90.00',
    averagePrice: '110.00', currentAvailability: 'in_stock', lastObservedAt: now, createdAt: now, updatedAt: now,
  }))
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
  api.getCatalog = async () => snapshot
  api.getCard = async id => {
    const card = cards.find(card=>card.id===id)
    if(!card) throw new Error('Карточка не найдена')
    return card
  }
  api.getChart = async () => ({points:[]})
  api.getHistory = async (id,days,page=1,pageSize=50) => ({card:await api.getCard(id),history:[],days,page,pageSize,totalCount:0,
    statistics:{cardId:id,days,averagePrice:'100.00',minimumPrice:'90.00',maximumPrice:'110.00',observationsCount:0,observedDays:0}})
  let lastGroupInput: unknown = null
  api.updateGroup = async (id,input) => {
    lastGroupInput=input
    const group=snapshot.groups.find(group=>group.id===id)!
    return {...group,...input}
  }
  // Suppress unrelated mock background runs in a timing fixture.
  api.listRuns = async () => []
  Object.assign(window, { __pwPerf: {
    snapshot,
    get lastGroupInput() { return lastGroupInput },
    progress: (successCount: number) => {
      const run = { id: 999999, status: 'running' as const, startedAt: now, finishedAt: null, totalCount: count,
        successCount, failureCount: 0, current: null, challenge: null, retryableCount: 0, diagnosticsStatus: 'complete' as const, retryScopeIncomplete: false }
      api.getRun = async () => run
      queryClient.setQueryData(['recent-runs'], [run])
      queryClient.setQueryData(['runs', run.id, false], run)
    },
  } })
}
