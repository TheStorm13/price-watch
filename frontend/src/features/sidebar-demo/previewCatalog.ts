import { compareMoney } from '../../utils/money'
import { compareItems, matchesItem, type DisplayItem } from '../cards/catalogItems'

/** Missing parameter means all; an explicit empty value means none. */
export function readPreviewSelection(params: URLSearchParams, key: string): string[] | null {
  return params.has(key) ? params.getAll(key).filter(Boolean) : null
}

export function comparePreviewItems(left: DisplayItem, right: DisplayItem, sort: string | null): number {
  if (sort !== 'price-asc' && sort !== 'price-desc') return compareItems(left, right, null)
  const a = left.card?.currentPrice, b = right.card?.currentPrice
  if (a == null || b == null) return a == null ? (b == null ? left.id - right.id : 1) : -1
  return compareMoney(a, b) * (sort === 'price-asc' ? 1 : -1) || left.id - right.id
}

export function selectPreviewItems(items: DisplayItem[], params: URLSearchParams): DisplayItem[] {
  const marketplaces = readPreviewSelection(params, 'markets')
  const tags = readPreviewSelection(params, 'tags')
  const deal = params.get('deals')
  return items.filter((item) => matchesItem(item, {
    query: (params.get('q') ?? '').trim().toLowerCase(), marketplace: 'all', status: 'all', tag: '',
    dealFilter: deal === 'deals' || deal === 'non_deals' ? deal : 'all',
  }) && (marketplaces === null || marketplaces.includes(item.card?.marketplace ?? ''))
    && (tags === null || tags.some((tag) => item.card?.tags?.includes(tag)))
    && (params.get('stock') !== '1' || item.card?.currentAvailability === 'in_stock'))
    .toSorted((a, b) => comparePreviewItems(a, b, params.get('sort')))
}

export function hasPreviewFilters(params: URLSearchParams) {
  return ['q', 'markets', 'tags', 'stock', 'deals', 'sort'].some((key) => params.has(key))
}
