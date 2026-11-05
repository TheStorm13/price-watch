import { compareMoney } from '../../utils/money'
import { cardItem, compareItems, matchesItem, type DisplayItem } from '../cards/catalogItems'
import type { CatalogSnapshot, Deal, TrackedCardView } from '../../types/domain'

export const previewMarketplaceOptions = [
  { value: 'ozon', label: 'Ozon' }, { value: 'wildberries', label: 'Wildberries' },
  { value: 'aliexpress', label: 'AliExpress' }, { value: 'yandex-market', label: 'Яндекс Маркет' },
]

/** Missing parameter means all; an empty tag selection means untagged products. */
export function readPreviewSelection(params: URLSearchParams, key: string): string[] | null {
  return params.has(key) ? params.getAll(key).filter(Boolean) : null
}

export function readPreviewMarketplaces(params: URLSearchParams): string[] | null {
  const requested = readPreviewSelection(params, 'markets')
  const valid = requested?.filter((value) => previewMarketplaceOptions.some((option) => option.value === value))
  return valid?.length && valid.length < previewMarketplaceOptions.length ? valid : null
}

export function comparePreviewItems(left: DisplayItem, right: DisplayItem, sort: string | null): number {
  if (sort !== 'price-asc' && sort !== 'price-desc') return compareItems(left, right, null)
  const a = left.card?.currentPrice, b = right.card?.currentPrice
  if (a == null || b == null) return a == null ? (b == null ? left.id - right.id : 1) : -1
  return compareMoney(a, b) * (sort === 'price-asc' ? 1 : -1) || left.id - right.id
}

export function selectPreviewItems(items: DisplayItem[], params: URLSearchParams): DisplayItem[] {
  const marketplaces = readPreviewMarketplaces(params)
  const tags = readPreviewSelection(params, 'tags')
  const deal = params.get('deals')
  return items.filter((item) => matchesItem(item, {
    query: (params.get('q') ?? '').trim().toLowerCase(), marketplace: 'all', status: 'all', tag: '',
    dealFilter: deal === 'deals' || deal === 'non_deals' ? deal : 'all',
  }) && (marketplaces === null || marketplaces.includes(item.card?.marketplace ?? ''))
    && (tags === null || (tags.length ? tags.some((tag) => item.card?.tags?.includes(tag)) : !item.card?.tags?.length))
    && (params.get('stock') !== '1' || item.card?.currentAvailability === 'in_stock'))
    .toSorted((a, b) => comparePreviewItems(a, b, params.get('sort')))
}

/** Filter cards first: no group may combine conditions matched by different members. */
export function buildPreviewCatalog(snapshot: CatalogSnapshot | undefined, params: URLSearchParams, deals: Map<number, Deal>) {
  const cards = snapshot?.cards ?? []
  const matching = selectPreviewItems(cards.map((card) => cardItem(card, deals)), params)
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
      savings: representative.savings, isDeal: representative.priority,
      hasMemberDeals: members.some((member) => deals.has(member.id)) }
    orderedItems.push({ kind: 'group', id: group.id, title: group.name, group, card,
      savings: representative.savings, priority: representative.priority, matchingCardCount: members.length })
  }
  orderedItems.sort((a, b) => comparePreviewItems(a, b, params.get('sort')))
  const availableTags = [...new Set(cards.flatMap((card) => card.tags ?? []))]
    .sort(new Intl.Collator('ru', { numeric: true, sensitivity: 'base' }).compare)
  return { orderedItems, groupedCards, availableTags, matchingCount: matching.length, totalCount: cards.length }
}

export function hasPreviewFilters(params: URLSearchParams) {
  return ['q', 'markets', 'tags', 'stock', 'deals', 'sort'].some((key) => params.has(key))
}
