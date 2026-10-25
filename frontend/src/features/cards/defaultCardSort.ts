import { compareMoney } from '../../utils/money'
import type { TrackedCardView } from '../../types/domain'

type CardSortValues = Pick<TrackedCardView, 'id' | 'currentAvailability' | 'currentPrice'>

function availabilityRank(card: CardSortValues): number {
  if (card.currentAvailability === 'in_stock') return 0
  if (card.currentAvailability === 'out_of_stock') return 1
  if (card.currentAvailability === 'unknown') return 2
  return 3
}

export function compareDefaultCards(
  left: CardSortValues, right: CardSortValues, savings: Map<number, string>,
): number {
  const availability = availabilityRank(left) - availabilityRank(right)
  if (availability) return availability

  const benefit = compareMoney(savings.get(right.id) ?? '0', savings.get(left.id) ?? '0')
  if (benefit) return benefit

  const leftPrice = left.currentPrice
  const rightPrice = right.currentPrice
  if (leftPrice === null || rightPrice === null) return leftPrice === null ? (rightPrice === null ? left.id - right.id : 1) : -1
  const priceOrder = compareMoney(leftPrice, rightPrice)
  if (priceOrder) return priceOrder
  return left.id - right.id
}
