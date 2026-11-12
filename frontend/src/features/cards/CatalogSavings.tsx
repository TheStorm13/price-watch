import { Star } from 'lucide-react'
import type { PurchaseAssessment } from '../../types/domain'
import { Popover, PopoverTrigger, PopoverContent, PopoverHeader, PopoverTitle } from '@/components/ui/popover'
import { formatDateTime, formatPrice } from '../../utils/format'
import { subtractMoney, type DecimalString } from '../../utils/money'

interface Props {
  assessment?: PurchaseAssessment | null
  observedAt?: string | null
  savings: DecimalString | null
  average?: DecimalString | null
  minimum?: DecimalString | null
}

export function CatalogSavings({ savings, average, minimum, assessment, observedAt }: Props) {
  const maximum = average != null && minimum != null ? subtractMoney(average, minimum) : null
  const content = <span className="catalog-savings">
    <span className={savings !== null ? 'deal-savings' : undefined}>{savings !== null ? formatPrice(savings) : average == null || minimum == null ? '—' : 'Нет выгоды'}</span>
    <span className="catalog-savings__maximum" title="Максимальная выгода: средняя цена минус минимальная">{formatPrice(maximum)}</span>
  </span>
  if (!assessment?.isMatch) return <span className="purchase-indicator">{content}</span>
  const a = assessment
  const days = a.historyStartedAt ? Math.floor((Date.parse(a.evaluatedAt) - Date.parse(a.historyStartedAt)) / 86400000) : 0
  return <Popover><PopoverTrigger asChild><button type="button" className="purchase-indicator purchase-indicator--match" aria-label="Почему товар подходит для покупки" onClick={event => event.stopPropagation()}>
    {content}<Star className="purchase-indicator__star" aria-hidden="true" />
  </button></PopoverTrigger>
    <PopoverContent className="w-80" onClick={event => event.stopPropagation()} aria-label="Условия покупки">
      <PopoverHeader><PopoverTitle>Подходит по вашим условиям</PopoverTitle></PopoverHeader>
      {a.matches.includes('small_range') ? <p>За {days} дней цена менялась от {formatPrice(a.minimumPrice)} до {formatPrice(a.maximumPrice)}. Разница {a.maximumPrice != null && a.minimumPrice != null ? formatPrice(subtractMoney(a.maximumPrice, a.minimumPrice)) : '—'} не больше вашего порога {formatPrice(a.smallRangeTolerance)}.</p> : null}
      {a.matches.includes('target_price') ? <p>Сейчас {formatPrice(a.currentPrice)} — не выше вашей целевой цены {formatPrice(a.targetPrice)}.</p> : null}
      {a.matches.includes('historical_savings_share') ? <p>Достигнута доля максимальной выгоды не меньше {a.historicalSavingsShare}%. Средняя {formatPrice(a.averagePrice)}, минимум {formatPrice(a.minimumPrice)}, сейчас {formatPrice(a.currentPrice)}. Ваш порог цены — {formatPrice(a.threshold)}.</p> : null}
      <p className="text-muted-foreground">Последнее наблюдение: {formatDateTime(observedAt ?? null)}. По наблюдаемой истории; будущие скидки могут быть другими.</p>
    </PopoverContent>
  </Popover>
}
