// Loaded only in the mock build, never in the desktop runtime.
import { api } from '../api/client'
import { queryClient } from '../app/providers'
import { performanceData } from './performanceData'

export function installPerformanceFixture() {
  const params = new URLSearchParams(location.search)
  const count = Number(params.get('perf'))
  if (![100, 1000, 5000].includes(count)) return
  const shape = params.get('shape') ?? 'plain'
  const now = new Date().toISOString()
  const snapshot = performanceData(count, shape, params.get('dataset') === 'varied', now)
  const cards = snapshot.cards
  api.getCatalog = async () => snapshot
  api.getCard = async id => {
    const card = cards.find(card=>card.id===id)
    if(!card) throw new Error('Карточка не найдена')
    return card
  }
  api.getVariants = async id => {
    const card=await api.getCard(id)
    return [{id,trackingEnabled: false, isTracked: true, cardId:id,externalId:card.externalId,title:'Основной вариант',url:null,options:{},currentPrice:card.currentPrice,currentAvailability:card.currentAvailability,lastObservedAt:now,updatedAt:now}]
  }
  api.getChart = async () => ({points:[]})
  api.getHistory = async (id,days,page=1,pageSize=50) => ({card:await api.getCard(id),history:[],days,page,pageSize,totalCount:0,
    statistics:{cardId:id,windowStart:'2024-10-01T00:00:00Z',windowEnd:now,averagePrice:'100.00',minimumPrice:'90.00',maximumPrice:'110.00',observationsCount:0,observedDays:0}})
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
