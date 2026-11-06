import { compareMoney, type DecimalString } from '../../utils/money'
import type { Deal, TrackedCardView, ProductGroup } from '../../types/domain'
import { catalogSavings } from './catalogSavings'

export const columnLabels = { title:'Карточка',marketplace:'Маркетплейс',price:'Цена',minimum:'Минимальная',average:'Средняя',savings:'Выгода / Максимальная выгода',availability:'Наличие' }
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

/** Default deals-first ordering, shared by individual cards and projected groups. */
export function compareItems(left: DisplayItem, right: DisplayItem): number {
  if (left.priority !== right.priority) return left.priority ? -1 : 1
  const availability = (item: DisplayItem) => item.card?.currentAvailability
    ? availabilityRanks[item.card.currentAvailability] : 3
  const order = Number(right.card?.dealsEnabled ?? false) - Number(left.card?.dealsEnabled ?? false)
    || availability(left) - availability(right)
    || compareNullableMoney(left.savings, right.savings, 'desc')
    || compareNullableMoney(left.card?.currentPrice ?? null, right.card?.currentPrice ?? null, 'asc')
  return order || collator.compare(left.kind, right.kind) || left.id - right.id
}

function compareNullableMoney(a: string | null, b: string | null, direction: 'asc' | 'desc') {
  if (a === null || b === null) return a === null ? (b === null ? 0 : 1) : -1
  return compareMoney(a, b) * (direction === 'asc' ? 1 : -1)
}
