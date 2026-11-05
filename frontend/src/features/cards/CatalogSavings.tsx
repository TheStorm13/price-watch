import { formatPrice } from '../../utils/format'
import { subtractMoney, type DecimalString } from '../../utils/money'

interface Props {
  savings: DecimalString | null
  average?: DecimalString | null
  minimum?: DecimalString | null
}

export function CatalogSavings({ savings, average, minimum }: Props) {
  const maximum = average != null && minimum != null ? subtractMoney(average, minimum) : null
  return <span className="catalog-savings">
    <span className={savings !== null ? 'deal-savings' : undefined}>{savings !== null ? formatPrice(savings) : 'Сейчас не выгодно'}</span>
    <span className="catalog-savings__maximum" title="Максимальная выгода: средняя цена минус минимальная">{formatPrice(maximum)}</span>
  </span>
}
