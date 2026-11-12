import { Star } from 'lucide-react'
import type { PurchaseAssessment } from '../../types/domain'
import { Popover, PopoverTrigger, PopoverContent, PopoverHeader, PopoverTitle } from '@/components/ui/popover'
import { formatPrice } from '../../utils/format'
import { subtractMoney, type DecimalString } from '../../utils/money'

interface Props {
  assessment?: PurchaseAssessment | null
  savings: DecimalString | null
  average?: DecimalString | null
  minimum?: DecimalString | null
}

export function CatalogSavings({ savings, average, minimum, assessment }: Props) {
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
      {a.matches.includes('small_range') ? <div className="purchase-reason">
        <p>За {days} дней колебания цены не больше вашего порога.</p>
        <span>Минимальная: {formatPrice(a.minimumPrice)}</span>
        <span>Максимальная: {formatPrice(a.maximumPrice)}</span>
        <span>Разница: {a.maximumPrice != null && a.minimumPrice != null ? formatPrice(subtractMoney(a.maximumPrice, a.minimumPrice)) : '—'}</span>
        <span>Ваш порог разницы: {formatPrice(a.smallRangeTolerance)}</span>
      </div> : null}
      {a.matches.includes('target_price') ? <div className="purchase-reason">
        <p>Цена сейчас не выше вашей целевой цены.</p>
        <span>Сейчас: {formatPrice(a.currentPrice)}</span>
        <span>Целевая цена: {formatPrice(a.targetPrice)}</span>
      </div> : null}
      {a.matches.includes('historical_savings_share') ? <div className="purchase-reason">
        <p>Достигнута доля максимальной выгоды не меньше {a.historicalSavingsShare}%.</p>
        <span>Средняя: {formatPrice(a.averagePrice)}</span>
        <span>Минимальная: {formatPrice(a.minimumPrice)}</span>
        <span>Сейчас: {formatPrice(a.currentPrice)}</span>
        <span>Ваш порог цены: {formatPrice(a.threshold)}</span>
      </div> : null}
      <p className="text-muted-foreground">По наблюдаемой истории; будущие скидки могут быть другими.</p>
    </PopoverContent>
  </Popover>
}
