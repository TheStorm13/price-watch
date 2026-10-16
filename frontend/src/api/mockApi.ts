import type {
  CardHistoryResponse,
  CollectionRun,
  CreateCardInput,
  Deal,
  MarketplaceCard,
  PriceHistoryPoint,
  TransferDocument,
  ImportSummary,
  Marketplace,
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
    isArchived: false,
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
    isArchived: false,
    currentPrice: 24990,
    currentAvailability: 'in_stock',
    lastObservedAt: new Date(now - 2 * 86_400_000).toISOString(),
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
    isArchived: false,
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
    isArchived: false,
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
    isArchived: false,
    currentPrice: 34990,
    currentAvailability: 'in_stock',
    lastObservedAt: new Date(now - 26 * 60 * 60_000).toISOString(),
    createdAt: new Date(now - 62 * 86_400_000).toISOString(),
    updatedAt: new Date(now - 26 * 60 * 60_000).toISOString(),
  },
]

const priceSeries = [81490, 80990, 79990, 79490, 78490, 76990, 75490, 74490, 73490, 72990]

let history: PriceHistoryPoint[] = [
  ...priceSeries.map((price, index) => ({
    id: index + 1,
    cardId: 1,
    collectionRunId: 21 - index,
    price,
    availability: 'in_stock' as const,
    observedAt: new Date(now - (priceSeries.length - 1 - index) * 3 * 86_400_000).toISOString(),
  })),
  ...cards.filter((card) => card.id !== 1 && card.currentPrice !== null && card.lastObservedAt !== null)
    .map((card, index) => ({
      id: priceSeries.length + index + 1, cardId: card.id, collectionRunId: 21,
      price: card.currentPrice, availability: card.currentAvailability ?? 'unknown' as const,
      observedAt: card.lastObservedAt as string,
    })),
]

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
    errors: [{
      cardId: 2, marketplace: 'ozon', externalId: '1478523690',
      at: new Date(now - 86_400_000 + 70_000).toISOString(),
      type: 'MarketplaceUnavailable', message: 'Не удалось получить страницу товара',
      traceback: 'MarketplaceUnavailable: Не удалось получить страницу товара',
    }],
  },
]

let nextCardId = 6
let nextRunId = 22
let nextHistoryId = Math.max(0, ...history.map((point) => point.id)) + 1
const runCreatedAt = new Map<number, number>()
const continuedRuns = new Set<number>()

const delay = <T>(value: T, milliseconds = 180) =>
  new Promise<T>((resolve) => window.setTimeout(() => resolve(value), milliseconds))

function mergeImportedCards(document: TransferDocument, apply: boolean): ImportSummary {
  if (document.version !== 1 || !Array.isArray(document.cards)) throw new Error('Неверный формат файла экспорта')
  const summary: ImportSummary = {
    cardsAdded: 0, cardsMerged: 0, observationsAdded: 0,
    observationsRemoved: 0, observationsSkipped: 0,
  }
  for (const importedCard of document.cards) {
    const current = cards.find((card) => card.marketplace === importedCard.marketplace && card.externalId === importedCard.externalId)
    const local = current ? history.filter((point) => point.cardId === current.id) : []
    const events = [
      ...local.map((point) => ({ ...point, source: 'local' as const, sourceId: point.id })),
      ...importedCard.history.map((point, sourceId) => ({
        ...point, price: point.price === null ? null : Number(point.price),
        source: 'import' as const, sourceId,
      })),
    ].sort((a, b) => Date.parse(a.observedAt) - Date.parse(b.observedAt) ||
      Number(a.source === 'import') - Number(b.source === 'import') || a.sourceId - b.sourceId)
    const merged: typeof events = []
    let previousTime: number | null = null
    let previousTimePrice: number | null = null
    for (const event of events) {
      const time = Date.parse(event.observedAt)
      if (time === previousTime) {
        if (event.price !== previousTimePrice) throw new Error(`Разные цены для одного времени: ${event.observedAt}`)
        continue
      }
      previousTime = time
      previousTimePrice = event.price
      if (merged.length && event.price !== null && merged.at(-1)?.price === event.price) continue
      merged.push(event)
    }
    const keptLocal = new Set(merged.filter((point) => point.source === 'local').map((point) => point.sourceId))
    const added = merged.filter((point) => point.source === 'import')
    summary[current ? 'cardsMerged' : 'cardsAdded'] += 1
    summary.observationsAdded += added.length
    summary.observationsRemoved += local.length - keptLocal.size
    summary.observationsSkipped += importedCard.history.length - added.length
    if (!apply) continue
    const card: MarketplaceCard = current ?? {
      id: nextCardId++, marketplace: importedCard.marketplace as Marketplace,
      externalId: importedCard.externalId, title: importedCard.title, url: importedCard.url,
      isActive: importedCard.isActive, isArchived: importedCard.isArchived ?? false,
      currentPrice: null, currentAvailability: null,
      lastObservedAt: null, createdAt: importedCard.createdAt, updatedAt: importedCard.createdAt,
    }
    if (!current) cards = [...cards, card]
    else if (Date.parse(importedCard.createdAt) < Date.parse(card.createdAt)) card.createdAt = importedCard.createdAt
    for (const point of importedCard.history) {
      if (Date.parse(point.observedAt) > Date.parse(card.updatedAt)) card.updatedAt = point.observedAt
    }
    history = history.filter((point) => point.cardId !== card.id || keptLocal.has(point.id))
    history.push(...added.map((point) => ({
      id: nextHistoryId++, cardId: card.id, collectionRunId: null,
      price: point.price, availability: point.availability,
      observedAt: point.observedAt,
    })))
    const latest = merged.at(-1)
    card.currentPrice = latest?.price ?? null
    card.currentAvailability = latest?.availability ?? null
    card.lastObservedAt = latest?.observedAt ?? null
  }
  return summary
}

export const mockApi = {
  async exportCards(): Promise<TransferDocument> {
    return delay({
      version: 1,
      cards: cards.map((card) => ({
        marketplace: card.marketplace,
        externalId: card.externalId,
        title: card.title,
        url: card.url,
        isActive: card.isActive,
        isArchived: card.isArchived,
        createdAt: card.createdAt,
        history: history.filter((point) => point.cardId === card.id)
          .sort((a, b) => Date.parse(a.observedAt) - Date.parse(b.observedAt))
          .map((point) => ({
            price: point.price === null ? null : point.price.toFixed(2),
            availability: point.availability,
            observedAt: point.observedAt,
          })),
      })),
    })
  },

  async previewImportCards(document: TransferDocument): Promise<ImportSummary> {
    return delay(mergeImportedCards(document, false))
  },

  async importCards(document: TransferDocument): Promise<ImportSummary> {
    return delay(mergeImportedCards(document, true))
  },

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
      isArchived: false,
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
    const savedPoints = history.filter((point) => point.cardId === cardId && Date.parse(point.observedAt) >= cutoff)
      .sort((a, b) => Date.parse(a.observedAt) - Date.parse(b.observedAt) || a.id - b.id)
    const points = savedPoints.length
      ? savedPoints
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

  async getChart(cardId: number, days: number) {
    const response = await this.getHistory(cardId, days, 1, Number.MAX_SAFE_INTEGER)
    return { points: response.history.toReversed().map((point) =>
      point.availability === 'out_of_stock' ? { ...point, price: null } : point) }
  },

  async listRuns() {
    return delay(runs.map((run) => ({ ...run, errors: null })))
  },

  async listDeals(): Promise<Deal[]> {
    return delay(cards.filter((card) => card.isActive && !card.isArchived && card.currentAvailability === 'in_stock' &&
      card.currentPrice !== null && Date.now() - Date.parse(card.createdAt) >= 7 * 86_400_000 &&
      card.id === 1).map((card) => ({ card, averagePrice: 78000,
      savings: 78000 - (card.currentPrice ?? 0), baselineDays: 8,
      lastCollectionRunId: history.at(-1)?.collectionRunId ?? null })))
  },

  async retryRun(runId: number): Promise<CollectionRun> {
    const source = runs.find((run) => run.id === runId)
    const targets = source?.errors?.filter((error) => error.cardId !== null) ?? []
    if (!source || targets.length === 0) throw new Error('Нет карточек для повтора')
    if (runs.some((run) => run.retryOfRunId === runId)) throw new Error('Повтор уже создан')
    const retry = await this.startRun(targets[0].cardId ?? undefined)
    const next = { ...retry, retryOfRunId: runId, totalCount: targets.length }
    runs = runs.map((run) => run.id === next.id ? next : run)
    return next
  },

  async startRun(cardId?: number) {
    const selected = cardId ? cards.filter((card) => card.id === cardId && card.isActive) : cards.filter((card) => card.isActive)
    if (!selected.length) throw new Error(cardId ? 'Активная карточка не найдена' : 'Нет активных карточек для сбора')
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

  async getRun(runId: number, includeErrors = false) {
    const index = runs.findIndex((item) => item.id === runId)
    if (index < 0) throw new Error('Запуск не найден')
    const run = runs[index]
    if (run.finishedAt) return delay({ ...run, errors: includeErrors ? run.errors ?? [] : null }, 80)
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
      cards = cards.map((card) => card.isActive ? {
        ...card,
        currentPrice: card.id === run.current?.cardId && card.currentPrice !== null
          ? card.currentPrice - 100 : card.currentPrice,
        lastObservedAt: observedAt, updatedAt: observedAt,
      } : card)
      const first = cards[0]
      if (first?.id === run.current?.cardId && first.currentPrice !== null && history.at(-1)?.price !== first.currentPrice) {
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
    return delay({ ...next, errors: includeErrors ? next.errors ?? [] : null }, 80)
  },

  async continueRun(runId: number) {
    continuedRuns.add(runId)
    const index = runs.findIndex((item) => item.id === runId)
    if (index < 0) throw new Error('Запуск не найден')
    runs[index] = { ...runs[index], status: 'running', challenge: null }
    return delay(runs[index])
  },
}
