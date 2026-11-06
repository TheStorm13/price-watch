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

export function compareCatalogItems(left: DisplayItem, right: DisplayItem, sort: string | null): number {
  const parsed = parseColumnSort(sort)
  if (!parsed) return compareItems(left, right)
  const { key, direction } = parsed
  const a = columnValue(left, key), b = columnValue(right, key)
  const tie = left.kind.localeCompare(right.kind) || left.id - right.id
  if (a === null || b === null) return a === null ? (b === null ? tie : 1) : -1
  const order = ['price', 'minimum', 'average', 'savings'].includes(key)
    ? compareMoney(a, b) : a.localeCompare(b, 'ru', { numeric: true, sensitivity: 'base' })
  return order * (direction === 'asc' ? 1 : -1) || tie
}

export function selectCatalogItems(items: DisplayItem[], params: URLSearchParams): DisplayItem[] {
  const marketplaces = readMarketplaces(params)
  const tags = readSelection(params, 'tags')
  const deal = params.get('deals')
  const query = (params.get('q') ?? '').trim().toLowerCase()
  return items.filter((item) => (!query || `${item.card?.title ?? ''} ${item.card?.externalId ?? ''}`.toLowerCase().includes(query))
    && (deal !== 'deals' || item.priority) && (deal !== 'non_deals' || !item.priority)
    && (marketplaces === null || marketplaces.includes(item.card?.marketplace ?? ''))
    && (tags === null || (tags.length ? tags.some((tag) => item.card?.tags?.includes(tag)) : !item.card?.tags?.length))
    && (params.get('stock') !== '1' || item.card?.currentAvailability === 'in_stock'))
    .toSorted((a, b) => compareCatalogItems(a, b, params.get('sort')))
}

/** Filter cards first: no group may combine conditions matched by different members. */
export function buildCatalog(snapshot: CatalogSnapshot | undefined, params: URLSearchParams, deals: Map<number, Deal>) {
  const cards = snapshot?.cards ?? []
  const matching = selectCatalogItems(cards.map((card) => cardItem(card, deals)), params)
  const groupIds = new Set(snapshot?.groups.map((group) => group.id))
  const groupedCards = new Map<number, TrackedCardView[]>()
  const orderedItems = matching.filter((item) => !groupIds.has(item.card?.groupId ?? -1))
  for (const item of matching) {
    const card = item.card!
    if (card.groupId == null || !groupIds.has(card.groupId)) continue
    const members = groupedCards.get(card.groupId) ?? []
    members.push(card)
    groupedCards.set(card.groupId, members)
  }
  for (const original of snapshot?.groups ?? []) {
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
  orderedItems.sort((a, b) => compareCatalogItems(a, b, params.get('sort')))
  const availableTags = [...new Set(cards.flatMap((card) => card.tags ?? []))]
    .sort(new Intl.Collator('ru', { numeric: true, sensitivity: 'base' }).compare)
  return { orderedItems, groupedCards, availableTags, matchingCount: matching.length, totalCount: cards.length }
}

export function hasCatalogFilters(params: URLSearchParams) {
  return ['q', 'markets', 'tags', 'stock', 'deals', 'sort'].some((key) => params.has(key))
}
