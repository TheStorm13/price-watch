import type { Availability, PurchaseAssessment, PurchaseSettings } from '../types/domain'
import { compareMoney, decimalParts, decimalText, subtractMoney } from '../utils/money'

export function validatePurchaseMoney(value: string | null, allowZero = false) {
  if (value === null) return
  const [coefficient, scale] = decimalParts(value)
  if (scale > 2 || coefficient < 0n || (!allowZero && coefficient === 0n) || compareMoney(value, '1000000000000') >= 0) throw new Error('Некорректная сумма')
}

export function mockAssessment(input: { price: string | null; availability: Availability | null; minimum: string | null;
  maximum: string | null; average: string | null; target: string | null; historyStartedAt: string | null; asOf: number }, settings: PurchaseSettings): PurchaseAssessment {
  const { price, availability, minimum, maximum, average, target, historyStartedAt, asOf } = input
  const historyEligible = historyStartedAt !== null && asOf - Date.parse(historyStartedAt) > 30 * 86400000
  let threshold: string | null = null
  if (average !== null && minimum !== null && compareMoney(average, minimum) > 0 && settings.historicalSavingsShare !== null) {
    const [gap, gs] = decimalParts(subtractMoney(average, minimum))
    const [share, ss] = decimalParts(settings.historicalSavingsShare)
    threshold = subtractMoney(average, decimalText(gap * share, gs + ss + 2))
  }
  const matches: PurchaseAssessment['matches'] = []
  if (availability === 'in_stock' && price !== null) {
    if (historyEligible && settings.smallRangeTolerance !== null && minimum !== null && maximum !== null
      && compareMoney(subtractMoney(maximum, minimum), settings.smallRangeTolerance) <= 0) matches.push('small_range')
    if (target !== null && compareMoney(price, target) <= 0) matches.push('target_price')
    if (historyEligible && threshold !== null && compareMoney(price, threshold) <= 0) matches.push('historical_savings_share')
  }
  return { evaluatedAt: new Date(asOf).toISOString(), historyStartedAt, historyEligible, isMatch: matches.length > 0, matches,
    currentPrice: price, minimumPrice: minimum, maximumPrice: maximum, averagePrice: average, targetPrice: target,
    smallRangeTolerance: settings.smallRangeTolerance, historicalSavingsShare: settings.historicalSavingsShare, threshold }
}
