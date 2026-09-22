import type {
  CardHistoryResponse,
  CollectionRun,
  CreateCardInput,
  MarketplaceCard,
  PriceHistoryPoint,
  UpdateCardInput,
} from '../types/domain'

const now = Date.now()

let cards: MarketplaceCard[] = [
  {
    id: 1,
    marketplace: 'ozon',
    externalId: '1604900984',
    title: 'Смартфон Samsung Galaxy S24',
    url: 'https://www.ozon.ru/product/1604900984',
    isActive: true,
    currentPrice: 72990,
    currentAvailability: 'in_stock',
    lastObservedAt: new Date(now - 5 * 60_000).toISOString(),
    createdAt: new Date(now - 45 * 86_400_000).toISOString(),
    updatedAt: new Date(now - 5 * 60_000).toISOString(),
  },
  {
    id: 2,
    marketplace: 'ozon',
    externalId: '1587342210',
    title: 'Наушники Apple AirPods Pro 2',
    url: 'https://www.ozon.ru/product/1587342210',
    isActive: true,
    currentPrice: 24990,
    currentAvailability: 'in_stock',
    lastObservedAt: new Date(now - 12 * 60_000).toISOString(),
    createdAt: new Date(now - 32 * 86_400_000).toISOString(),
    updatedAt: new Date(now - 12 * 60_000).toISOString(),
  },
  {
    id: 3,
    marketplace: 'ozon',
    externalId: '1620013375',
    title: 'Умные часы Xiaomi Watch S3',
    url: 'https://www.ozon.ru/product/1620013375',
    isActive: true,
    currentPrice: 12490,
    currentAvailability: 'out_of_stock',
    lastObservedAt: new Date(now - 60 * 60_000).toISOString(),
    createdAt: new Date(now - 18 * 86_400_000).toISOString(),
    updatedAt: new Date(now - 60 * 60_000).toISOString(),
  },
  {
    id: 4,
    marketplace: 'ozon',
    externalId: '1598827711',
    title: 'Пылесос Dyson V12 Detect Slim',
    url: 'https://www.ozon.ru/product/1598827711',
    isActive: true,
    currentPrice: null,
    currentAvailability: null,
    lastObservedAt: null,
    createdAt: new Date(now - 3 * 86_400_000).toISOString(),
    updatedAt: new Date(now - 3 * 86_400_000).toISOString(),
  },
  {
    id: 5,
    marketplace: 'ozon',
    externalId: '1579984456',
    title: 'Конструктор LEGO Technic McLaren P1',
    url: 'https://www.ozon.ru/product/1579984456',
    isActive: false,
    currentPrice: 34990,
    currentAvailability: 'in_stock',
    lastObservedAt: new Date(now - 26 * 60 * 60_000).toISOString(),
    createdAt: new Date(now - 62 * 86_400_000).toISOString(),
    updatedAt: new Date(now - 26 * 60 * 60_000).toISOString(),
  },
]

const priceSeries = [81490, 80990, 79990, 79490, 78490, 76990, 75490, 74490, 73490, 72990]

let history: PriceHistoryPoint[] = priceSeries.map((price, index) => ({
  id: index + 1,
  cardId: 1,
  collectionRunId: 21 - index,
  price,
  availability: 'in_stock',
  observedAt: new Date(now - (priceSeries.length - 1 - index) * 3 * 86_400_000).toISOString(),
}))

let runs: CollectionRun[] = [
  {
    id: 21,
    status: 'completed',
    totalCount: 4,
    successCount: 4,
    failureCount: 0,
    current: null,
    challenge: null,
    startedAt: new Date(now - 5 * 60_000).toISOString(),
    finishedAt: new Date(now - 4 * 60_000 - 26_000).toISOString(),
  },
  {
    id: 20,
    status: 'completed_with_errors',
    totalCount: 4,
    successCount: 3,
    failureCount: 1,
    current: null,
    challenge: null,
    startedAt: new Date(now - 86_400_000).toISOString(),
    finishedAt: new Date(now - 86_400_000 + 76_000).toISOString(),
  },
]

let nextCardId = 6
let nextRunId = 22
const runCreatedAt = new Map<number, number>()
const continuedRuns = new Set<number>()

const delay = <T>(value: T, milliseconds = 180) =>
  new Promise<T>((resolve) => window.setTimeout(() => resolve(value), milliseconds))

export const mockApi = {
  async listCards() {
    return delay([...cards])
  },

  async getCard(cardId: number) {
    const card = cards.find((item) => item.id === cardId)
    if (!card) throw new Error('Карточка не найдена')
    return delay({ ...card })
  },

  async createCard(input: CreateCardInput) {
    if (cards.some((card) => card.marketplace === input.marketplace && card.externalId === input.externalId)) {
      const error = new Error('Такая карточка уже добавлена') as Error & { field?: string }
      error.field = 'externalId'
      throw error
    }
    const createdAt = new Date().toISOString()
    const card: MarketplaceCard = {
      id: nextCardId++,
      marketplace: input.marketplace,
      externalId: input.externalId,
      title: input.title?.trim() || null,
      url: input.url?.trim() || null,
      isActive: true,
      currentPrice: null,
      currentAvailability: null,
      lastObservedAt: null,
      createdAt,
      updatedAt: createdAt,
    }
    cards = [...cards, card]
    return delay(card)
  },

  async updateCard(cardId: number, input: UpdateCardInput) {
    let updated: MarketplaceCard | undefined
    cards = cards.map((card) => {
      if (card.id !== cardId) return card
      updated = { ...card, ...input, updatedAt: new Date().toISOString() }
      return updated
    })
    if (!updated) throw new Error('Карточка не найдена')
    return delay(updated)
  },

  async deleteCard(cardId: number) {
    if (!cards.some((card) => card.id === cardId)) throw new Error('Карточка не найдена')
    cards = cards.filter((card) => card.id !== cardId)
    history = history.filter((point) => point.cardId !== cardId)
    return delay(undefined)
  },

  async getHistory(cardId: number, days: number, page = 1, pageSize = 50): Promise<CardHistoryResponse> {
    const card = cards.find((item) => item.id === cardId)
    if (!card) throw new Error('Карточка не найдена')
    const cutoff = Date.now() - days * 86_400_000
    const points = cardId === 1
      ? history.filter((point) => Date.parse(point.observedAt) >= cutoff)
      : card.currentPrice === null
        ? []
        : [{
            id: 1000 + card.id,
            cardId: card.id,
            collectionRunId: 21,
            price: card.currentPrice,
            availability: card.currentAvailability ?? 'unknown',
            observedAt: card.lastObservedAt ?? new Date().toISOString(),
          } satisfies PriceHistoryPoint]
    const priced = points.flatMap((point) => point.price === null ? [] : [point.price])
    return delay({
      card,
      statistics: {
        cardId,
        days,
        averagePrice: priced.length ? Math.round(priced.reduce((sum, price) => sum + price, 0) / priced.length) : null,
        minimumPrice: priced.length ? Math.min(...priced) : null,
        maximumPrice: priced.length ? Math.max(...priced) : null,
        observationsCount: priced.length,
        observedDays: priced.length,
      },
      history: points.slice((page - 1) * pageSize, page * pageSize).toReversed(),
      page,
      pageSize,
      totalCount: points.length,
    })
  },

  async listRuns() {
    return delay([...runs])
  },

  async startRun(cardId?: number) {
    const selected = cardId ? cards.filter((card) => card.id === cardId && card.isActive) : cards.filter((card) => card.isActive)
    const run: CollectionRun = {
      id: nextRunId++,
      status: 'queued',
      totalCount: selected.length,
      successCount: 0,
      failureCount: 0,
      current: selected[0]
        ? { cardId: selected[0].id, marketplace: selected[0].marketplace, externalId: selected[0].externalId }
        : null,
      challenge: null,
      startedAt: new Date().toISOString(),
      finishedAt: null,
    }
    runs = [run, ...runs]
    runCreatedAt.set(run.id, Date.now())
    return delay(run)
  },

  async getRun(runId: number) {
    const index = runs.findIndex((item) => item.id === runId)
    if (index < 0) throw new Error('Запуск не найден')
    const run = runs[index]
    if (run.finishedAt) return delay(run, 80)
    const elapsed = Date.now() - (runCreatedAt.get(runId) ?? Date.now())
    let next = run
    if (elapsed > 5_000 && !continuedRuns.has(runId)) {
      next = {
        ...run,
        status: 'waiting_for_user',
        successCount: Math.min(1, run.totalCount),
        challenge: {
          type: 'browser_verification',
          message: 'Завершите проверку в открывшемся Chrome, затем продолжите',
        },
      }
    } else if (continuedRuns.has(runId) && elapsed > 7_500) {
      next = {
        ...run,
        status: 'completed',
        successCount: run.totalCount,
        current: null,
        challenge: null,
        finishedAt: new Date().toISOString(),
      }
      const observedAt = new Date().toISOString()
      cards = cards.map((card) => card.isActive ? { ...card, lastObservedAt: observedAt, updatedAt: observedAt } : card)
      const first = cards[0]
      if (first?.currentPrice !== null) {
        history = [...history, {
          id: history.length + 1,
          cardId: first.id,
          collectionRunId: runId,
          price: first.currentPrice,
          availability: first.currentAvailability ?? 'unknown',
          observedAt,
        }]
      }
    } else if (elapsed > 900) {
      next = { ...run, status: 'running' }
    }
    runs[index] = next
    return delay(next, 80)
  },

  async continueRun(runId: number) {
    continuedRuns.add(runId)
    const index = runs.findIndex((item) => item.id === runId)
    if (index < 0) throw new Error('Запуск не найден')
    runs[index] = { ...runs[index], status: 'running', challenge: null }
    return delay(runs[index])
  },
}
