import { compareMoney } from '../../utils/money'
import { cardItem, compareItems, parseColumnSort, type ColumnSortKey, type DisplayItem } from './catalogItems'
import type { CatalogSnapshot, Deal, TrackedCardView } from '../../types/domain'

export const marketplaceOptions = [
  { value: 'ozon', label: 'Ozon' }, { value: 'wildberries', label: 'Wildberries' },
  { value: 'aliexpress', label: 'AliExpress' }, { value: 'yandex-market', label: 'Яндекс Маркет' },
]

/** Missing parameter means all; an empty tag selection means untagged products. */
export function readSelection(params: URLSearchParams, key: string): string[] | null {
  return params.has(key) ? [...new Set(params.getAll(key).filter(Boolean))] : null
}

export function readMarketplaces(params: URLSearchParams): string[] | null {
  const requested = readSelection(params, 'markets')
  const valid = requested === null ? null : [...new Set(requested.filter((value) => marketplaceOptions.some((option) => option.value === value)))]
  return valid?.length && valid.length < marketplaceOptions.length ? valid : null
}

function columnValue(item: DisplayItem, key: ColumnSortKey): string | null {
  if (key === 'title') return item.title
  if (key === 'savings') return item.savings
  if (key === 'price') return item.card?.currentPrice ?? null
  if (key === 'minimum') return item.card?.minimumPrice ?? null
  if (key === 'average') return item.card?.averagePrice ?? null
  if (key === 'marketplace') return marketplaceOptions.find(option => option.value === item.card?.marketplace)?.label ?? null
  return item.card?.currentAvailability === 'in_stock' ? '0' : '1'
}

const collator = new Intl.Collator('ru', { numeric: true, sensitivity: 'base' })

export function catalogTags(cards: readonly TrackedCardView[]) {
  return [...new Set(cards.flatMap(card => card.tags ?? []))].sort(collator.compare)
}

export function catalogComparator(sort: string | null) {
  const parsed = parseColumnSort(sort)
  if (!parsed) return compareItems
  const { key, direction } = parsed
  const sign = direction === 'asc' ? 1 : -1
  const money = ['price', 'minimum', 'average', 'savings'].includes(key)
  return (left: DisplayItem, right: DisplayItem): number => {
    const a = columnValue(left, key), b = columnValue(right, key)
    const tie = (left.kind === right.kind ? 0 : left.kind === 'card' ? -1 : 1) || left.id - right.id
    if (a === null || b === null) return a === null ? (b === null ? tie : 1) : -1
    return (money ? compareMoney(a, b) : collator.compare(a, b)) * sign || tie
  }
}

/** Only values that affect products; view and fixture/navigation parameters are excluded. */
export function catalogFilterKey(params: URLSearchParams) {
  const next = new URLSearchParams()
  const query = (params.get('q') ?? '').trim().toLowerCase()
  if (query) next.set('q', query)
  const marketplaces = readMarketplaces(params)
  if (marketplaces !== null) for (const value of marketplaces.toSorted()) next.append('markets', value)
  const tags = readSelection(params, 'tags')
  if (tags !== null) for (const value of tags.length ? tags.toSorted() : ['']) next.append('tags', value)
  if (params.get('stock') === '1') next.set('stock', '1')
  const deal = params.get('deals')
  if (deal === 'deals' || deal === 'non_deals') next.set('deals', deal)
  const sort = params.get('sort')
  if (parseColumnSort(sort)) next.set('sort', sort!)
  return next.toString()
}

export function selectCatalogItems(items: DisplayItem[], params: URLSearchParams, compare = catalogComparator(params.get('sort'))): DisplayItem[] {
  const marketplaces = readMarketplaces(params)
  const tags = readSelection(params, 'tags')
  const deal = params.get('deals')
  const query = (params.get('q') ?? '').trim().toLowerCase()
  const stock = params.get('stock') === '1'
  return items.filter((item) => (!query || `${item.card?.title ?? ''} ${item.card?.externalId ?? ''}`.toLowerCase().includes(query))
    && (deal !== 'deals' || item.priority) && (deal !== 'non_deals' || !item.priority)
    && (marketplaces === null || marketplaces.includes(item.card?.marketplace ?? ''))
    && (tags === null || (tags.length ? tags.some((tag) => item.card?.tags?.includes(tag)) : !item.card?.tags?.length))
    && (!stock || item.card?.currentAvailability === 'in_stock'))
    .toSorted(compare)
}

/** Filter cards first: no group may combine conditions matched by different members. */
export function prepareCatalog(snapshot: CatalogSnapshot | undefined, deals: Map<number, Deal>) {
  const cards = snapshot?.cards ?? []
  const groups = snapshot?.groups ?? []
  return { items: cards.map(card => cardItem(card, deals)), groups, groupIds: new Set(groups.map(group => group.id)), deals }
}

export function buildCatalog(prepared: ReturnType<typeof prepareCatalog>, params: URLSearchParams) {
  const { items, groups, groupIds, deals } = prepared
  const compare = catalogComparator(params.get('sort'))
  const matching = selectCatalogItems(items, params, compare)
  const groupedCards = new Map<number, TrackedCardView[]>()
  const orderedItems = groupIds.size === 0 ? matching : matching.filter((item) => !groupIds.has(item.card?.groupId ?? -1))
  for (const item of matching) {
    const card = item.card!
    if (card.groupId == null || !groupIds.has(card.groupId)) continue
    const members = groupedCards.get(card.groupId) ?? []
    members.push(card)
    groupedCards.set(card.groupId, members)
  }
  for (const original of groups) {
    const members = groupedCards.get(original.id)
    const card = members?.[0]
    if (!card) continue
    const representative = cardItem(card, deals)
    const group = { ...original, representativeCard: card, representativeCardId: card.id,
      currentPrice: card.currentPrice, minimumPrice: card.minimumPrice ?? null,
      savings: representative.savings, baselineDays: deals.get(card.id)?.baselineDays ?? 0, isDeal: representative.priority,
      hasMemberDeals: members.some((member) => deals.has(member.id)) }
    orderedItems.push({ kind: 'group', id: group.id, title: group.name, group, card,
      savings: representative.savings, priority: representative.priority, matchingCardCount: members.length })
  }
  if (groupedCards.size) orderedItems.sort(compare)
  return { orderedItems, groupedCards, matchingCount: matching.length, totalCount: items.length }
}

export function hasCatalogFilters(params: URLSearchParams) {
  return ['q', 'markets', 'tags', 'stock', 'deals', 'sort'].some((key) => params.has(key))
}
