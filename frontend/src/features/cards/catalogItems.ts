import { compareMoney, type DecimalString } from '../../utils/money'
import type { Deal, TrackedCardView, ProductGroup } from '../../types/domain'
import { catalogSavings } from './catalogSavings'

export const columnLabels = { title:'Товар',savings:'Выгода / макс.',price:'Цена',minimum:'Минимальная',average:'Средняя',marketplace:'Маркетплейс',availability:'Наличие' }
export type ColumnSortKey = keyof typeof columnLabels
export function parseColumnSort(value: string | null): { key: ColumnSortKey; direction: 'asc' | 'desc' } | null {
  const parts = (value ?? '').split('-')
  if (parts.length !== 2) return null
  const [key, direction] = parts
  if (!Object.hasOwn(columnLabels, key)) return null
  if (direction !== 'asc' && direction !== 'desc') return null
  return { key: key as ColumnSortKey, direction }
}
export type DisplayItem = {
  kind: 'card'; id: number; title: string; card: TrackedCardView; savings: DecimalString | null; priority: boolean
} | {
  kind: 'group'; id: number; title: string; card: TrackedCardView | null; group: ProductGroup
  savings: DecimalString | null; priority: boolean; matchingCardCount: number
}
const availabilityRanks = { in_stock: 0, out_of_stock: 1, unknown: 2 }
const collator = new Intl.Collator('ru', { numeric: true, sensitivity: 'base' })

export function cardItem(card: TrackedCardView, deals: Map<number, Deal>): DisplayItem {
  const deal = deals.get(card.id)
  return { kind: 'card', id: card.id, title: card.title ?? card.externalId, card,
    savings: catalogSavings(card, deal?.savings ?? null), priority: !!deal }
}

export function compareParticipation(left: DisplayItem, right: DisplayItem): number {
  return Number(right.card?.dealsEnabled ?? false) - Number(left.card?.dealsEnabled ?? false)
}

/** Participation first by default, then exact savings; shared by cards and groups. */
export function compareItems(left: DisplayItem, right: DisplayItem, participationFirst = true): number {
  const availability = (item: DisplayItem) => item.card?.currentAvailability
    ? availabilityRanks[item.card.currentAvailability] : 3
  const order = (participationFirst ? compareParticipation(left, right) : 0)
    || compareNullableMoney(left.savings, right.savings, 'desc')
    || availability(left) - availability(right)
    || compareNullableMoney(left.card?.currentPrice ?? null, right.card?.currentPrice ?? null, 'asc')
  return order || collator.compare(left.kind, right.kind) || left.id - right.id
}

function compareNullableMoney(a: string | null, b: string | null, direction: 'asc' | 'desc') {
  if (a === null || b === null) return a === null ? (b === null ? 0 : 1) : -1
  return compareMoney(a, b) * (direction === 'asc' ? 1 : -1)
}
