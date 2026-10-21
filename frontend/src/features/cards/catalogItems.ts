import type { Deal, MarketplaceCard, ProductGroup } from '../../types/domain'
import { availabilityLabel, marketplaceLabel } from '../../utils/format'

export const columnSortKeys = ['title', 'marketplace', 'price', 'minimum', 'average', 'savings', 'availability'] as const
export type ColumnSortKey = typeof columnSortKeys[number]
export type Sort = { key: ColumnSortKey | 'updated'; direction: 'asc' | 'desc' } | null
export type DisplayItem = {
  kind: 'card'; id: number; title: string; card: MarketplaceCard; savings: number | null; priority: boolean
} | {
  kind: 'group'; id: number; title: string; card: MarketplaceCard | null; group: ProductGroup
  savings: number | null; priority: boolean
}
const availabilityRanks = { in_stock: 0, out_of_stock: 1, unknown: 2 }
const collator = new Intl.Collator('ru', { numeric: true, sensitivity: 'base' })

export function cardItem(card: MarketplaceCard, deals: Map<number, Deal>): DisplayItem {
  const deal = deals.get(card.id)
  return { kind: 'card', id: card.id, title: card.title ?? card.externalId, card,
    savings: deal?.savings ?? null, priority: !!deal }
}

export function catalogItems(cards: MarketplaceCard[], groups: ProductGroup[], deals: Map<number, Deal>): DisplayItem[] {
  const groupIds = new Set(groups.map((group) => group.id))
  return [
    ...groups.map((group): DisplayItem => ({ kind: 'group', id: group.id, title: group.name, group,
      card: group.representativeCard, savings: group.savings, priority: group.isDeal || group.hasMemberDeals })),
    ...cards.filter((card) => !groupIds.has(card.groupId ?? -1)).map((card) => cardItem(card, deals)),
  ]
}

export function parseSort(value: string | null): Sort {
  if (!value) return null
  const parts = value.split('-')
  if (parts.length !== 2) return null
  const [key, direction] = parts
  if (direction !== 'asc' && direction !== 'desc') return null
  if (columnSortKeys.includes(key as ColumnSortKey) || key === 'updated' && direction === 'desc') {
    return { key: key as NonNullable<Sort>['key'], direction }
  }
  return null
}

export function matchesItem(item: DisplayItem, filters: {
  query: string; marketplace: string; status: string; tag: string; dealsOnly: boolean
}): boolean {
  const card = item.card
  const text = `${item.title} ${card?.title ?? ''} ${card?.externalId ?? ''}`.toLowerCase()
  if (filters.query && !text.includes(filters.query)) return false
  if (filters.marketplace !== 'all' && card?.marketplace !== filters.marketplace) return false
  if (filters.tag && !card?.tags?.includes(filters.tag)) return false
  if (filters.dealsOnly && item.savings === null) return false
  if (filters.status === 'deals_disabled') return !(card?.dealsEnabled ?? false)
  if (filters.status === 'no_data') return !card?.lastObservedAt
  return filters.status === 'all' || card?.currentAvailability === filters.status
}

function sortValue(item: DisplayItem, key: NonNullable<Sort>['key']): string | number | null {
  const card = item.card
  if (key === 'title') return item.title
  if (key === 'savings') return item.savings
  if (!card) return null
  if (key === 'marketplace') return marketplaceLabel[card.marketplace]
  if (key === 'price') return card.currentPrice
  if (key === 'minimum') return card.minimumPrice ?? null
  if (key === 'average') return card.averagePrice ?? null
  if (key === 'updated') return card.lastObservedAt ? Date.parse(card.updatedAt) : null
  return card.currentAvailability ? availabilityLabel[card.currentAvailability] : null
}

function compareValue(first: string | number | null, second: string | number | null, direction: 'asc' | 'desc'): number {
  if (first === null || second === null) return first === null ? (second === null ? 0 : 1) : -1
  const order = typeof first === 'number' && typeof second === 'number'
    ? first - second : collator.compare(String(first), String(second))
  return direction === 'asc' ? order : -order
}

export function compareItems(left: DisplayItem, right: DisplayItem, sort: Sort): number {
  if (left.priority !== right.priority) return left.priority ? -1 : 1
  let order = 0
  if (sort) order = compareValue(sortValue(left, sort.key), sortValue(right, sort.key), sort.direction)
  else {
    const availability = (item: DisplayItem) => item.card?.currentAvailability
      ? availabilityRanks[item.card.currentAvailability] : 3
    order = Number(right.card?.dealsEnabled ?? false) - Number(left.card?.dealsEnabled ?? false)
      || availability(left) - availability(right)
      || compareValue(left.savings, right.savings, 'desc')
      || compareValue(left.card?.currentPrice ?? null, right.card?.currentPrice ?? null, 'asc')
  }
  return order || collator.compare(left.kind, right.kind) || left.id - right.id
}
