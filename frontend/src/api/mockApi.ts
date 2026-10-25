import { compareMoney, priceText } from '../utils/money'
import { subtractMoney } from './mockMoney'
import { historyMetrics, priceMetrics } from './mockPriceMetrics'
import type {
  CardHistoryResponse,
  CollectionRun,
  CreateCardInput,
  Deal,
  TrackedCardView,
  PriceHistoryPoint,
  TransferDocument,
  ImportSummary,
  Marketplace,
  UpdateCardInput,
  ProductGroup,
  GroupInput,
} from '../types/domain'

const now = Date.now()

let cards: TrackedCardView[] = [
  {
    id: 1,
    marketplace: 'ozon',
    externalId: '1604900984',
    title: 'Смартфон Samsung Galaxy S24',
    url: 'https://www.ozon.ru/product/1604900984',
    imageUrl: null,
    dealsEnabled: true,
    currentPrice: "72990.00",
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
    imageUrl: null,
    dealsEnabled: true,
    currentPrice: "24990.00",
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
    imageUrl: null,
    dealsEnabled: true,
    currentPrice: "12490.00",
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
    imageUrl: null,
    dealsEnabled: true,
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
    imageUrl: null,
    dealsEnabled: false,
    currentPrice: "34990.00",
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
    price: price.toFixed(2),
    availability: 'in_stock' as const,
    observedAt: new Date(now - (priceSeries.length - 1 - index) * 3 * 86_400_000 - 5 * 60_000).toISOString(),
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
    retryableCount: 0,
    retryScopeIncomplete: false,
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
    retryableCount: 1,
    retryScopeIncomplete: false,
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
let groups: { id: number; name: string; tags: string[] }[] = []
let nextGroupId = 1

function cardMetrics(card: TrackedCardView) {
  return priceMetrics(history.filter((point) => point.cardId === card.id))
}

function cardView(card: TrackedCardView): TrackedCardView {
  const metrics = cardMetrics(card)
  return { ...card, currentPrice: metrics.latest?.price ?? null,
    currentAvailability: metrics.latest?.availability ?? null,
    lastObservedAt: metrics.latest?.observedAt ?? null,
    minimumPrice: metrics.minimumPrice, averagePrice: metrics.averagePrice }
}

function cardDeal(card: TrackedCardView): Deal | null {
  const view = cardView(card)
  const metrics = cardMetrics(card)
  if (!view.dealsEnabled || view.currentAvailability !== 'in_stock' || view.currentPrice === null
    || metrics.averagePrice === null || compareMoney(view.currentPrice, metrics.averagePrice) >= 0) return null
  return { card: view, averagePrice: metrics.averagePrice, savings: subtractMoney(metrics.averagePrice, view.currentPrice),
    baselineDays: metrics.baselineDays, lastCollectionRunId: metrics.latest?.collectionRunId ?? null }
}

function groupView(group: { id: number; name: string; tags: string[] }): ProductGroup {
  const members = cards.filter((card) => card.groupId === group.id).map(cardView)
  const representative = members.toSorted((a, b) => Number(a.currentPrice === null) - Number(b.currentPrice === null)
    || compareMoney(a.currentPrice ?? '0', b.currentPrice ?? '0') || a.id - b.id)[0] ?? null
  const deal = representative ? cardDeal(representative) : null
  return { ...group, cardIds: members.map((card) => card.id).sort((a, b) => a - b),
    representativeCardId: representative?.id ?? null, representativeCard: representative,
    currentPrice: representative?.currentPrice ?? null, minimumPrice: representative?.minimumPrice ?? null,
    savings: deal?.savings ?? null, isDeal: !!deal,
    baselineDays: representative ? cardMetrics(representative).baselineDays : 0,
    hasMemberDeals: members.some((card) => !!cardDeal(card)) }
}

function assignGroup(groupId: number, cardIds: number[]) {
  if (new Set(cardIds).size !== cardIds.length || cardIds.some((id) => !cards.some((card) => card.id === id))) {
    throw new Error('Одна или несколько карточек не найдены')
  }
  cards = cards.map((card) => ({ ...card, groupId: cardIds.includes(card.id) ? groupId : card.groupId === groupId ? null : card.groupId }))
}
let nextRunId = 22
let nextHistoryId = Math.max(0, ...history.map((point) => point.id)) + 1
const runCreatedAt = new Map<number, number>()
const runTargetIds = new Map<number, number[]>()
const continuedRuns = new Set<number>()

const delay = <T>(value: T, milliseconds = 180) =>
  new Promise<T>((resolve) => window.setTimeout(() => resolve(value), milliseconds))

function mergeImportedCards(document: TransferDocument, apply: boolean): ImportSummary {
  if (document.version !== 2 || !Array.isArray(document.cards)) throw new Error('Неверный формат файла экспорта')
  const cardFields = new Set(['marketplace', 'externalId', 'title', 'url', 'imageUrl', 'tags', 'dealsEnabled', 'createdAt', 'history'])
  if (document.cards.some((card) => typeof card.dealsEnabled !== 'boolean' ||
    Object.keys(card).some((field) => !cardFields.has(field)))) {
    throw new Error('Неверный формат карточки в файле экспорта')
  }
  const summary: ImportSummary = {
    cardsAdded: 0, cardsMerged: 0, observationsAdded: 0,
    observationsRemoved: 0, observationsSkipped: 0, groupsAdded: 0,
  }
  const importedGroups = document.groups ?? []
  const available = new Set(document.cards.map((card) => `${card.marketplace}:${card.externalId}`))
  const assigned = new Set<string>()
  for (const group of importedGroups) {
    for (const member of group.cards) {
      const key = `${member.marketplace}:${member.externalId}`
      if (!available.has(key) || assigned.has(key)) throw new Error('Некорректный состав групп в файле')
      assigned.add(key)
    }
  }
  summary.groupsAdded = new Set(importedGroups.map((group) => group.name)
    .filter((name) => !groups.some((group) => group.name === name))).size
  for (const importedCard of document.cards) {
    const current = cards.find((card) => card.marketplace === importedCard.marketplace && card.externalId === importedCard.externalId)
    const local = current ? history.filter((point) => point.cardId === current.id) : []
    const events = [
      ...local.map((point) => ({ ...point, source: 'local' as const, sourceId: point.id })),
      ...importedCard.history.map((point, sourceId) => ({
        ...point, price: point.price === null ? null : priceText(point.price),
        source: 'import' as const, sourceId,
      })),
    ].sort((a, b) => Date.parse(a.observedAt) - Date.parse(b.observedAt) ||
      Number(a.source === 'import') - Number(b.source === 'import') || a.sourceId - b.sourceId)
    const merged: typeof events = []
    let previousTime: number | null = null
    let previousTimePrice: string | null = null
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
    const card: TrackedCardView = current ?? {
      id: nextCardId++, marketplace: importedCard.marketplace as Marketplace,
      externalId: importedCard.externalId, title: importedCard.title, url: importedCard.url,
      tags: importedCard.tags ?? [],
      imageUrl: importedCard.imageUrl ?? null,
      dealsEnabled: importedCard.dealsEnabled,
      currentPrice: null, currentAvailability: null,
      lastObservedAt: null, createdAt: importedCard.createdAt, updatedAt: importedCard.createdAt,
    }
    if (!current) cards = [...cards, card]
    else {
      if (Date.parse(importedCard.createdAt) < Date.parse(card.createdAt)) card.createdAt = importedCard.createdAt
      card.imageUrl ||= importedCard.imageUrl ?? null
      card.tags = [...new Set([...(card.tags ?? []), ...(importedCard.tags ?? [])])].slice(0, 2)
    }
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
  if (apply) {
    for (const imported of importedGroups) {
      let group = groups.find((item) => item.name === imported.name)
      if (!group) {
        group = { id: nextGroupId++, name: imported.name, tags: imported.tags ?? [] }
        groups = [...groups, group]
      } else {
        group.tags = [...new Set([...group.tags, ...(imported.tags ?? [])])]
      }
      for (const member of imported.cards) {
        const card = cards.find((item) => item.marketplace === member.marketplace && item.externalId === member.externalId)
        if (card && card.groupId == null) card.groupId = group.id
      }
    }
  }
  return summary
}

export const mockApi = {
  async getCatalog() {
    return delay({ cards: cards.map(cardView), groups: groups.map(groupView),
      deals: cards.flatMap((card) => { const deal = cardDeal(card); return deal ? [deal] : [] })
        .toSorted((a, b) => compareMoney(b.savings, a.savings) || a.card.id - b.card.id) })
  },
  async createGroup(input: GroupInput) {
    const group = { id: nextGroupId++, name: input.name.trim(), tags: input.tags ?? [] }
    if (!group.name) throw new Error('Укажите название группы')
    assignGroup(group.id, input.cardIds)
    groups = [...groups, group]
    return delay(groupView(group))
  },
  async updateGroup(id: number, input: GroupInput) {
    const group = groups.find((item) => item.id === id)
    if (!group) throw new Error('Группа не найдена')
    const name = input.name.trim()
    if (!name) throw new Error('Укажите название группы')
    assignGroup(id, input.cardIds)
    group.name = name
    group.tags = input.tags ?? []
    return delay(groupView(group))
  },
  async deleteGroup(id: number) {
    if (!groups.some((item) => item.id === id)) throw new Error('Группа не найдена')
    groups = groups.filter((item) => item.id !== id)
    cards = cards.map((card) => card.groupId === id ? { ...card, groupId: null } : card)
    return delay(undefined)
  },
  async exportCards(): Promise<TransferDocument> {
    return delay({
      version: 2,
      groups: groups.map((group) => ({
        name: group.name,
        tags: group.tags,
        cards: cards.filter((card) => card.groupId === group.id)
          .map((card) => ({ marketplace: card.marketplace, externalId: card.externalId })),
      })),
      cards: cards.map((card) => ({
        marketplace: card.marketplace,
        externalId: card.externalId,
        title: card.title,
        url: card.url,
        imageUrl: card.imageUrl,
        tags: card.tags ?? [],
        dealsEnabled: card.dealsEnabled,
        createdAt: card.createdAt,
        history: history.filter((point) => point.cardId === card.id)
          .sort((a, b) => Date.parse(a.observedAt) - Date.parse(b.observedAt))
          .map((point) => ({
            price: point.price === null ? null : priceText(point.price),
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

  async getCard(cardId: number) {
    const card = cards.find((item) => item.id === cardId)
    if (!card) throw new Error('Карточка не найдена')
    return delay(cardView(card))
  },

  async createCard(input: CreateCardInput) {
    if (cards.some((card) => card.marketplace === input.marketplace && card.externalId === input.externalId)) {
      const error = new Error('Такая карточка уже добавлена') as Error & { field?: string }
      error.field = 'externalId'
      throw error
    }
    const createdAt = new Date().toISOString()
    const card: TrackedCardView = {
      id: nextCardId++,
      marketplace: input.marketplace,
      externalId: input.externalId,
      title: input.title?.trim() || null,
      url: input.url?.trim() || null,
      imageUrl: null,
      tags: input.tags ?? [],
      dealsEnabled: true,
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
    let updated: TrackedCardView | undefined
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
    const metrics = historyMetrics(points)
    return delay({
      card,
      statistics: {
        cardId,
        days,
        averagePrice: metrics.averagePrice,
        minimumPrice: metrics.minimumPrice,
        maximumPrice: metrics.maximumPrice,
        observationsCount: metrics.observationsCount,
        observedDays: metrics.baselineDays,
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

  async retryRun(runId: number): Promise<CollectionRun> {
    const source = runs.find((run) => run.id === runId)
    const targets = source?.errors?.filter((error) => error.cardId !== null) ?? []
    if (!source || targets.length === 0) throw new Error('Нет карточек для повтора')
    if (runs.some((run) => run.retryOfRunId === runId)) throw new Error('Повтор уже создан')
    const retry = await this.startRun(targets[0].cardId ?? undefined)
    const next = { ...retry, retryOfRunId: runId, totalCount: targets.length }
    runs = runs.map((run) => run.id === next.id ? next : run.id === runId ? { ...run, retryableCount: 0 } : run)
    return next
  },

  async startRun(cardId?: number) {
    const selected = cardId ? cards.filter((card) => card.id === cardId) : cards.filter((card) => card.marketplace === 'ozon')
    if (!selected.length) throw new Error(cardId ? 'Карточка не найдена' : 'Нет карточек для сбора')
    if (selected.some((card) => card.marketplace !== 'ozon')) throw new Error('Для этого маркетплейса коннектор ещё не подключён')
    const run: CollectionRun = {
      id: nextRunId++,
      retryableCount: 0,
      retryScopeIncomplete: false,
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
    runTargetIds.set(run.id, selected.map((card) => card.id))
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
      const targets = new Set(runTargetIds.get(runId) ?? [])
      cards = cards.map((card) => targets.has(card.id) ? {
        ...card,
        currentPrice: card.id === run.current?.cardId && card.currentPrice !== null
          ? priceText(subtractMoney(card.currentPrice, '100')) : card.currentPrice,
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
    next = { ...next, retryableCount: ['failed', 'completed_with_errors'].includes(next.status) ? (next.errors?.filter((e) => e.cardId !== null).length ?? 0) : 0 }
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
