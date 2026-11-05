import type { TrackedCardView } from '../../types/domain'
import { compareMoney, subtractMoney, type DecimalString } from '../../utils/money'

/** Participation controls deal selection, not the displayed price difference. */
export function catalogSavings(card: TrackedCardView | null, dealSavings: DecimalString | null): DecimalString | null {
  if (!card || card.dealsEnabled) return dealSavings
  if (card.currentAvailability !== 'in_stock' || card.averagePrice == null || card.currentPrice == null) return null
  return compareMoney(card.averagePrice, card.currentPrice) > 0
    ? subtractMoney(card.averagePrice, card.currentPrice) : null
}
