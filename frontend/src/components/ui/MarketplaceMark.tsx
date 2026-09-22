import type { Marketplace } from '../../types/domain'
import { marketplaceLabel } from '../../utils/format'

export function MarketplaceMark({ marketplace }: { marketplace: Marketplace }) {
  return (
    <span className="marketplace-mark">
      <span className={`marketplace-mark__logo marketplace-mark__logo--${marketplace}`} aria-hidden="true">
        {marketplace === 'ozon' ? 'ozon' : marketplace === 'wildberries' ? 'WB' : 'Ali'}
      </span>
      <span>{marketplaceLabel[marketplace]}</span>
    </span>
  )
}
