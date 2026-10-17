import type { MarketplaceCard } from '../../types/domain'

type CardSortValues = Pick<MarketplaceCard, 'id' | 'currentAvailability' | 'currentPrice'>

function availabilityRank(card: CardSortValues): number {
  if (card.currentAvailability === 'in_stock') return 0
  if (card.currentAvailability === 'out_of_stock') return 1
  if (card.currentAvailability === 'unknown') return 2
  return 3
}

export function compareDefaultCards(
  left: CardSortValues, right: CardSortValues, savings: Map<number, number>,
): number {
  const availability = availabilityRank(left) - availabilityRank(right)
  if (availability) return availability

  const benefit = (savings.get(right.id) ?? 0) - (savings.get(left.id) ?? 0)
  if (benefit) return benefit

  const leftPrice = left.currentPrice ?? Infinity
  const rightPrice = right.currentPrice ?? Infinity
  if (leftPrice !== rightPrice) return leftPrice - rightPrice
  return left.id - right.id
}
