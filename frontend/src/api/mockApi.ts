import { parseYandexMarketUrl } from '../features/cards/yandexMarketIdentity'
import { parseAliExpressUrl } from '../features/cards/aliexpressIdentity'
import { parseWildberriesUrl } from '../features/cards/wildberriesIdentity'
import { parseOzonUrl } from '../features/cards/ozonIdentity'
import { compareMoney, priceText, subtractMoney } from '../utils/money'
import { historyMetrics, priceMetrics } from './mockPriceMetrics'
import type {
  CardHistoryResponse,
  CollectionRun,
  CreateCardInput,
  Deal,
  TrackedCardView,
  TrackedVariant,
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

let variants: TrackedVariant[] = cards.map((c) => ({ id: c.id, cardId: c.id, externalId: c.externalId,
  trackingEnabled: false, isTracked: true, title: 'Основной вариант', productTitle: c.title, imageUrl: c.imageUrl, options: {}, url: c.url, currentPrice: c.currentPrice,
  currentAvailability: c.currentAvailability, lastObservedAt: c.lastObservedAt, updatedAt: c.lastObservedAt ? c.updatedAt : null }))
cards = cards.map((c) => ({ ...c, primaryVariantId: c.id }))
history = history.map((p) => ({ ...p, variantId: p.cardId }))
let nextVariantId = 6

function validateVariant(marketplace: string, externalId: string, url: string | null) {
  if (marketplace === 'yandex-market') {
    if (!/^[1-9][0-9]{0,19}$/.test(externalId) || (url && parseYandexMarketUrl(url) !== externalId)) throw new Error('Ссылка не соответствует SKU Маркета')
    return
  }
  if (marketplace === 'ozon') {
    if (!/^[0-9]+$/.test(externalId) || (url && parseOzonUrl(url) !== externalId)) throw new Error('Ссылка не соответствует артикулу выбранного варианта Ozon')
    return
  }
  if (!['wildberries', 'aliexpress'].includes(marketplace)) return
  const [article, sku] = externalId.split(':')
  if (externalId.split(':').length > 2 || !/^[0-9]+$/.test(article) || (sku !== undefined && !/^[0-9]+$/.test(sku))) throw new Error('Укажите числовой артикул товара')
  if (url) {
    const ref = marketplace === 'wildberries' ? parseWildberriesUrl(url) : parseAliExpressUrl(url)
    const actual = 'nmId' in ref ? `${ref.nmId}:${ref.optionId}` : `${ref.productId}:${ref.skuId}`
    const linkedArticle = 'nmId' in ref ? ref.nmId : ref.productId
    const linkedSku = 'optionId' in ref ? ref.optionId : ref.skuId
    if (linkedArticle !== article || (sku && linkedSku && actual !== externalId)) throw new Error('Ссылка не соответствует товару и варианту')
  }
}

function variantView(v: TrackedVariant): TrackedVariant {
  const metrics = priceMetrics(history.filter((h) => h.variantId === v.id))
  return { ...v, currentPrice: metrics.latest?.price ?? null, currentAvailability: metrics.latest?.availability ?? null,
    lastObservedAt: metrics.latest?.observedAt ?? null }
}

let runs: CollectionRun[] = [
  {
    id: 21,
    retryableCount: 0,
    diagnosticsStatus: 'complete', retryScopeIncomplete: false,
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
    diagnosticsStatus: 'complete', retryScopeIncomplete: false,
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
  return priceMetrics(history.filter((point) => point.variantId === card.primaryVariantId))
}

function cardView(card: TrackedCardView): TrackedCardView {
  const metrics = cardMetrics(card)
  const primary = variants.find((v) => v.id === card.primaryVariantId)
  return { ...card, title: primary?.productTitle ?? null, options: primary?.options ?? {}, url: primary?.url ?? null, imageUrl: primary?.imageUrl ?? null, lastCollectedAt: primary?.updatedAt ?? null, currentPrice: metrics.latest?.price ?? null,
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
runs[0] = {...runs[0],status:'completed_with_errors',successCount:3,failureCount:1,retryableCount:1,errors:runs[1].errors}
const retryTargetIds = new Map(runs.map(run => [run.id, (run.errors ?? []).flatMap(error => error.cardId === null ? [] : [error.cardId])]))
runs = runs.map((run,index) => index===0 ? run : {...run,errors:[],diagnosticsStatus:'expired'})
const runTargetIds = new Map<number, number[]>()
const runVariantIds = new Map<number, number[]>()
const continuedRuns = new Set<number>()

const delay = <T>(value: T, milliseconds = 180) =>
  new Promise<T>((resolve) => window.setTimeout(() => resolve(value), milliseconds))

function mergeImportedCards(document: TransferDocument, apply: boolean): ImportSummary {
  if (document.version !== 3 || !Array.isArray(document.cards)) throw new Error('Используйте формат экспорта v3')
  const summary: ImportSummary = { cardsAdded: 0, cardsMerged: 0, observationsAdded: 0, observationsRemoved: 0, observationsSkipped: 0, groupsAdded: 0 }
  const available = new Set(document.cards.map((c) => `${c.marketplace}:${c.externalId}`))
  if (available.size !== document.cards.length) throw new Error('Повторные карточки')
  const assigned = new Set<string>()
  const skuOwners = new Map<string, string>()
  for (const imported of document.cards.filter((c) => ['ozon', 'yandex-market'].includes(c.marketplace))) {
    validateVariant(imported.marketplace, imported.externalId, null)
    if (!imported.variants.some((v) => v.externalId === imported.externalId)) throw new Error('Исходный SKU отсутствует в товаре')
    for (const v of imported.variants) {
      validateVariant(imported.marketplace, v.externalId, v.url)
      const localOwner = variants.find((member) => member.externalId === v.externalId && cards.some((c) => c.id === member.cardId && c.marketplace === imported.marketplace))
      if (skuOwners.has(`${imported.marketplace}:${v.externalId}`) || (localOwner && cards.find((c) => c.id === localOwner.cardId)?.externalId !== imported.externalId)) throw new Error(`SKU ${v.externalId} уже принадлежит другой карточке`)
      skuOwners.set(`${imported.marketplace}:${v.externalId}`, imported.externalId)
    }
  }
  for (const g of document.groups ?? []) for (const ref of g.cards) {
    const key = `${ref.marketplace}:${ref.externalId}`
    if (!available.has(key) || assigned.has(key)) throw new Error('Некорректный состав групп')
    assigned.add(key)
  }
  for (const imported of document.cards) {
    if (typeof imported.dealsEnabled !== 'boolean' || !imported.variants.length) throw new Error('Некорректная карточка')
    const refs = new Set<string>()
    for (const v of imported.variants) {
      validateVariant(imported.marketplace as Marketplace, v.externalId, v.url)
      const article = ['aliexpress','wildberries'].includes(imported.marketplace) ? v.externalId.split(':')[0] : v.externalId
      if ((imported.marketplace !== 'ozon' && article !== imported.externalId) || refs.has(v.externalId)) throw new Error('Повторный или чужой вариант')
      refs.add(v.externalId)
    }
    if (!refs.has(imported.primaryExternalId)) throw new Error('Главный вариант отсутствует')
    let card = cards.find((c) => c.marketplace === imported.marketplace && c.externalId === imported.externalId)
    summary[card ? 'cardsMerged' : 'cardsAdded'] += 1
    if (!card && apply) {
      card = { id: nextCardId++, marketplace: imported.marketplace as Marketplace, externalId: imported.externalId,
        title: imported.title, url: imported.url, imageUrl: imported.imageUrl ?? null, tags: imported.tags ?? [], dealsEnabled: imported.dealsEnabled,
        currentPrice: null, currentAvailability: null, lastObservedAt: null, createdAt: imported.createdAt, updatedAt: imported.createdAt }
      cards.push(card)
    }
    for (const incoming of imported.variants) {
      let variant = card ? variants.find((v) => v.cardId === card!.id && v.externalId === incoming.externalId) : undefined
      const local = variant ? history.filter((h) => h.variantId === variant!.id) : []
      const events = [...local.map((h) => ({ ...h, source: 'local' as const, sourceId: h.id })),
        ...incoming.history.map((h, sourceId) => ({ ...h, price: h.price === null ? null : priceText(h.price), source: 'import' as const, sourceId }))]
        .sort((a,b) => Date.parse(a.observedAt)-Date.parse(b.observedAt) || Number(a.source==='import')-Number(b.source==='import') || a.sourceId-b.sourceId)
      const merged: typeof events = []
      for (const event of events) {
        if (event.price !== null && compareMoney(event.price, '0') < 0) throw new Error('Некорректная цена')
        const last = merged.at(-1)
        if (last && Date.parse(event.observedAt) === Date.parse(last.observedAt)) {
          if (event.price !== last.price || event.availability !== last.availability) throw new Error('Разные наблюдения для одного времени')
          continue
        }
        if (last && event.price === last.price && event.availability === last.availability) continue
        merged.push(event)
      }
      const kept = new Set(merged.filter((h) => h.source === 'local').map((h) => h.sourceId))
      const added = merged.filter((h) => h.source === 'import')
      summary.observationsAdded += added.length
      summary.observationsRemoved += local.length-kept.size
      summary.observationsSkipped += incoming.history.length-added.length
      if (!apply || !card) continue
      if (!variant) {
        variant = { id: nextVariantId++, cardId: card.id, trackingEnabled: incoming.trackingEnabled ?? false, isTracked: false, externalId: incoming.externalId, title: incoming.title ?? '', productTitle: incoming.productTitle ?? (incoming.externalId === imported.primaryExternalId ? imported.title : null), imageUrl: incoming.imageUrl ?? (incoming.externalId === imported.primaryExternalId ? imported.imageUrl ?? null : null), options: incoming.options ?? {}, url: incoming.url,
          updatedAt: incoming.updatedAt ?? null, currentPrice: null, currentAvailability: null, lastObservedAt: null }
        variants.push(variant)
      }
      variant.imageUrl ??= incoming.imageUrl ?? (incoming.externalId === imported.primaryExternalId ? imported.imageUrl ?? null : null)
      variant.productTitle ??= incoming.productTitle ?? (incoming.externalId === imported.primaryExternalId ? imported.title : null)
      if (incoming.externalId === imported.primaryExternalId) card.primaryVariantId = variant.id
      history = history.filter((h) => h.variantId !== variant!.id || kept.has(h.id))
      history.push(...added.map((h) => ({ id: nextHistoryId++, cardId: card!.id, variantId: variant!.id, collectionRunId: null,
        price: h.price, availability: h.availability, observedAt: h.observedAt })))
    }
  }
  for (const incoming of document.groups ?? []) {
    let group = groups.find((g) => g.name === incoming.name)
    if (!group) {
      summary.groupsAdded! += 1
      if (!apply) continue
      group = { id: nextGroupId++, name: incoming.name, tags: incoming.tags ?? [] }
      groups.push(group)
    }
    if (apply) for (const ref of incoming.cards) {
      const card = cards.find((c) => c.marketplace === ref.marketplace && c.externalId === ref.externalId)
      if (card && card.groupId == null) card.groupId = group.id
    }
  }
  return summary
}

// Mock transport prepares fixture images only; it does not verify the live renderer.
export const mockApi = {
  async getThumbnail(cardId: number, profile: 'list' | 'tile' | 'detail', scale: number, variantId?: number): Promise<Blob> {
    const card = cards.find((item) => item.id === cardId)
    const source = variantId === undefined ? (card && cardView(card).imageUrl)
      : variants.find((item) => item.id === variantId && item.cardId === cardId)?.imageUrl
    if (!source) throw new Error('Image not found')
    const image = new Image()
    image.crossOrigin = 'anonymous'
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve()
      image.onerror = () => reject(new Error('Image unavailable'))
      image.src = source
    })
    const canvas = document.createElement('canvas')
    const [width, height] = { list: [51, 68], tile: [276, 368], detail: [384, 512] }[profile]
    canvas.width = Math.round(width * scale)
    canvas.height = Math.round(height * scale)
    const ratio = Math.min(1, canvas.width / image.naturalWidth, canvas.height / image.naturalHeight)
    const fittedWidth = Math.max(1, Math.round(image.naturalWidth * ratio))
    const fittedHeight = Math.max(1, Math.round(image.naturalHeight * ratio))
    const context = canvas.getContext('2d')!
    context.drawImage(image, Math.floor((canvas.width - fittedWidth) / 2), Math.floor((canvas.height - fittedHeight) / 2), fittedWidth, fittedHeight)
    return new Promise((resolve, reject) => canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error('PNG unavailable')), 'image/png'))
  },
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
      version: 3,
      groups: groups.map((g) => ({ name: g.name, tags: g.tags, cards: cards.filter((c) => c.groupId === g.id).map((c) => ({ marketplace:c.marketplace,externalId:c.externalId })) })),
      cards: cards.map(cardView).map((c) => ({ marketplace:c.marketplace, externalId:c.externalId, title:c.title,url:c.url,imageUrl:c.imageUrl,tags:c.tags,
        dealsEnabled:c.dealsEnabled,createdAt:c.createdAt,primaryExternalId:variants.find((v) => v.id === c.primaryVariantId)!.externalId,
        variants:variants.filter((v) => v.cardId === c.id).map((v) => ({ externalId:v.externalId,trackingEnabled:v.trackingEnabled,title:v.title,url:v.url,imageUrl:v.imageUrl ?? null,productTitle:v.productTitle ?? null,options:v.options,updatedAt:v.updatedAt,
          history:history.filter((h) => h.variantId === v.id).toSorted((a,b) => Date.parse(a.observedAt)-Date.parse(b.observedAt)).map((h) => ({ price:h.price,availability:h.availability,observedAt:h.observedAt })) })) })),
    })
  },

  async previewImportCards(document: TransferDocument): Promise<ImportSummary> {
    return delay(mergeImportedCards(document, false))
  },

  async importCards(document: TransferDocument): Promise<ImportSummary> {
    // Validate the entire document before applying; restore on any mutation failure.
    mergeImportedCards(document, false)
    const saved = structuredClone({ cards, variants, history, groups, nextCardId, nextVariantId, nextHistoryId, nextGroupId })
    try { return delay(mergeImportedCards(document, true)) }
    catch (error) { ({ cards, variants, history, groups, nextCardId, nextVariantId, nextHistoryId, nextGroupId } = saved); throw error }
  },

  async setVariantTracking(cardId: number, enabled: boolean, variantId?: number) {
    const card = cards.find((c) => c.id === cardId)
    if (!card) throw new Error('Карточка не найдена')
    if (variantId !== undefined && (!variants.some((v) => v.id === variantId && v.cardId === cardId) || variantId === card.primaryVariantId)) throw new Error('Главный или чужой вариант нельзя изменить')
    for (const v of variants) {
      if (v.cardId === cardId && v.id !== card.primaryVariantId && (variantId === undefined || v.id === variantId)) v.trackingEnabled = enabled
    }
    return mockApi.getVariants(cardId)
  },

  async getVariants(cardId: number) {
    if (!cards.some((c) => c.id === cardId)) throw new Error('Карточка не найдена')
    return delay(variants.filter((v) => v.cardId === cardId).map((v) => ({ ...variantView(v), isTracked: v.trackingEnabled || v.id === cards.find((c) => c.id === cardId)?.primaryVariantId })))
  },

  async getCard(cardId: number) {
    const card = cards.find((item) => item.id === cardId)
    if (!card) throw new Error('Карточка не найдена')
    return delay(cardView(card))
  },

  async createCard(input: CreateCardInput) {
    validateVariant(input.marketplace,input.externalId,input.url ?? null)
    if (['ozon', 'yandex-market'].includes(input.marketplace) && variants.some((v) => v.externalId === input.externalId && cards.some((c) => c.id === v.cardId && c.marketplace === input.marketplace))) {
      throw Object.assign(new Error('Такой вариант уже добавлен'), { field: 'externalId' })
    }
    const article = ['aliexpress','wildberries'].includes(input.marketplace) ? input.externalId.split(':')[0] : input.externalId
    let card = cards.find((c) => c.marketplace === input.marketplace && c.externalId === article)
    if (card && (input.externalId === article || variants.some((v) => v.cardId === card!.id && v.externalId === input.externalId))) {
      throw Object.assign(new Error('Такой вариант уже добавлен'), { field: 'externalId' })
    }
    const at = new Date().toISOString()
    if (!card) {
      card = { id:nextCardId++, marketplace:input.marketplace,externalId:article,title:input.title?.trim() || null,url:input.url || null,imageUrl:null,
        tags:input.tags ?? [],dealsEnabled:true,currentPrice:null,currentAvailability:null,lastObservedAt:null,createdAt:at,updatedAt:at }
      cards.push(card)
    }
    const variant: TrackedVariant = { id:nextVariantId++,cardId:card.id,trackingEnabled:false,isTracked:true,externalId:input.externalId,title:'',productTitle:input.title ?? null,imageUrl:null,options:{},url:input.url || null,
      currentPrice:null,currentAvailability:null,lastObservedAt:null,updatedAt:null }
    variants.push(variant)
    card.primaryVariantId ??= variant.id
    await mockApi.startRun(card.id, true)
    return delay(cardView(card))
  },

  async updateCard(cardId: number, input: UpdateCardInput) {
    const card = cards.find((c) => c.id === cardId)
    if (!card) throw new Error('Карточка не найдена')
    const selected = variants.find((v) => v.id === (input.primaryVariantId ?? card.primaryVariantId))
    if (!selected || selected.cardId !== cardId) throw new Error('Вариант не принадлежит этому товару')
    const url = 'url' in input ? input.url ?? null : selected.url
    validateVariant(card.marketplace,selected.externalId,url)
    Object.assign(card,input,{url,updatedAt:new Date().toISOString()})
    if ('url' in input) selected.url=url
    if ('title' in input) selected.productTitle=input.title ?? null
    return delay(cardView(card))
  },

  async deleteCard(cardId: number) {
    if (!cards.some((card) => card.id === cardId)) throw new Error('Карточка не найдена')
    cards = cards.filter((card) => card.id !== cardId)
    history = history.filter((point) => point.cardId !== cardId)
    variants = variants.filter((v) => v.cardId !== cardId)
    return delay(undefined)
  },

  async getHistory(cardId: number, days: number, page = 1, pageSize = 50, variantId?: number): Promise<CardHistoryResponse> {
    const card = cards.find((item) => item.id === cardId)
    if (!card) throw new Error('Карточка не найдена')
    const cutoff = Date.now() - days * 86_400_000
    const savedPoints = history.filter((point) => point.cardId === cardId && point.variantId === (variantId ?? card.primaryVariantId) && Date.parse(point.observedAt) >= cutoff)
      .sort((a, b) => Date.parse(a.observedAt) - Date.parse(b.observedAt) || a.id - b.id)
    const points = savedPoints
    const metrics = historyMetrics(points)
    return delay({
      card: cardView(card),
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
    const cutoff=Date.now()-days*86400000
    return delay({ points: history.filter((h) => h.cardId === cardId && Date.parse(h.observedAt) >= cutoff)
      .toSorted((a,b) => Date.parse(a.observedAt)-Date.parse(b.observedAt)).map((h) => h.availability === 'out_of_stock' ? {...h,price:null} : h) })
  },

  async listRuns() {
    return delay(runs.map((run) => ({ ...run, errors: null })))
  },

  async retryRun(runId: number): Promise<CollectionRun> {
    const source = runs.find((run) => run.id === runId)
    const targets = retryTargetIds.get(runId) ?? []
    if (!source || targets.length === 0) throw new Error('Нет карточек для повтора')
    if (runs.some((run) => run.retryOfRunId === runId)) throw new Error('Повтор уже создан')
    const retry = await this.startRun(targets[0])
    const next = { ...retry, retryOfRunId: runId, totalCount: targets.length }
    runs = runs.map((run) => run.id === next.id ? next : run.id === runId ? { ...run, retryableCount: 0 } : run)
    return next
  },

  async startRun(cardId?: number, discoverAll = false) {
    const selected = cardId ? cards.filter((card) => card.id === cardId) : cards
    if (!selected.length) throw new Error(cardId ? 'Карточка не найдена' : 'Нет карточек для сбора')
    const selectedVariants = variants.filter((v) => selected.some((c) => c.id === v.cardId && (discoverAll || c.primaryVariantId === v.id || v.trackingEnabled)))
    const run: CollectionRun = {
      id: nextRunId++,
      retryableCount: 0,
      diagnosticsStatus: 'complete', retryScopeIncomplete: false,
      status: 'queued',
      totalCount: selectedVariants.length,
      successCount: 0,
      failureCount: 0,
      current: selected[0]
        ? { cardId: selected[0].id, marketplace: selected[0].marketplace, externalId: selected[0].externalId }
        : null,
      challenge: null,
      startedAt: new Date().toISOString(),
      finishedAt: null,
    }
    runs = [run, ...runs.map(previous => ({...previous, errors: [], diagnosticsStatus: 'expired' as const}))]
    runCreatedAt.set(run.id, Date.now())
    runTargetIds.set(run.id, selected.map((card) => card.id))
    runVariantIds.set(run.id, selectedVariants.map((v) => v.id))
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
      variants=variants.map((v)=>(runVariantIds.get(runId) ?? []).includes(v.id)?{...v,updatedAt:observedAt}:v)
      const first = cards[0]
      if (first?.id === run.current?.cardId && first.currentPrice !== null && history.at(-1)?.price !== first.currentPrice) {
        history = [...history, {
          id: nextHistoryId++, variantId: first.primaryVariantId,
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
    next = { ...next, retryableCount: ['failed', 'completed_with_errors'].includes(next.status) ? (retryTargetIds.get(next.id)?.length ?? 0) : 0 }
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
