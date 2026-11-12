import { memo } from 'react'
import { ChevronRight, ChevronDown, Folders, Pencil } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { TableRow, TableCell } from '@/components/ui/table'
import { MarketplaceMark } from '../../components/product/MarketplaceMark'
import { AvailabilityStatus } from '../../components/product/AvailabilityStatus'
import { TagList } from '../../components/product/TagList'
import { dealStatus } from './CatalogProduct'
import { formatPrice } from '../../utils/format'
import type { ProductGroup } from '../../types/domain'
import { catalogSavings } from './catalogSavings'
import { CatalogSavings } from './CatalogSavings'

function groupDetails(group: ProductGroup) {
  const card = group.representativeCard
  if (card?.dealsEnabled !== false && !(group.hasMemberDeals && !group.isDeal)) return null
  return <div className="product-group__status">
    {card ? dealStatus(card) : null}
    {group.hasMemberDeals && !group.isDeal ? <Badge variant="secondary">Есть выгодный товар</Badge> : null}
  </div>
}

interface Props {
  group: ProductGroup; view: 'list' | 'grid'; collapsed: boolean; blockEnd: boolean
  onToggle: (id: number) => void; onEdit: (group: ProductGroup) => void
  index: number; measure?: (element: HTMLTableRowElement | null) => void
  matchingCardCount: number
}

export const CatalogGroup = memo(function CatalogGroup({ group, view, collapsed, blockEnd, onToggle, onEdit, index, measure, matchingCardCount }: Props) {
  const card = group.representativeCard
  const identity = <div className="product-group__identity">
    <Button variant="ghost" type="button" size="icon" className="product-group__toggle" aria-label={`${collapsed ? 'Раскрыть' : 'Свернуть'} группу ${group.name}`} aria-expanded={!collapsed} onClick={() => onToggle(group.id)}>
      {collapsed ? <ChevronRight data-icon="inline-start" /> : <ChevronDown data-icon="inline-start" />}
    </Button>
      <span className="product-group__heading">
        <span className="product-group__label"><Folders aria-hidden="true" />Группа · {matchingCardCount} из {group.cardIds.length} товаров</span>
        <strong>{group.name}</strong>
      </span>
    <div className="product-group__tags"><TagList tags={card?.tags} /></div>
    {groupDetails(group)}
  </div>
  const edit = <Button variant="ghost" size="icon-sm" type="button" aria-label={`Изменить группу ${group.name}`} onClick={() => onEdit(group)}><Pencil /></Button>

  if (view === 'grid') return <div className="product-group__header">
    {identity}
    <div className="product-group__metrics">
      <dl>
        <div><dt>Цена</dt><dd>{formatPrice(group.currentPrice)}</dd></div>
        <div><dt>Минимальная</dt><dd>{formatPrice(group.minimumPrice)}</dd></div>
        <div><dt>Средняя</dt><dd>{formatPrice(card?.averagePrice)}</dd></div>
        <div><dt>Выгода</dt><dd><CatalogSavings assessment={card?.purchaseAssessment} observedAt={card?.lastObservedAt} savings={catalogSavings(card, group.savings)} average={card?.averagePrice} minimum={group.minimumPrice} /></dd></div>
      </dl>
      <div className="product-group__availability">{card ? <MarketplaceMark marketplace={card.marketplace} /> : null}<AvailabilityStatus value={card?.currentAvailability ?? null} /></div>
    </div>
    {edit}
  </div>

  return <TableRow data-index={index} data-vrow={index} aria-rowindex={index + 2} ref={measure}
    data-block-start data-block-end={blockEnd || undefined} className="cards-table__group">
    <TableCell className="cards-table__selection py-0" />
    <TableCell className="py-0">{identity}</TableCell>
    <TableCell className="py-0"><CatalogSavings assessment={card?.purchaseAssessment} observedAt={card?.lastObservedAt} savings={catalogSavings(card, group.savings)} average={card?.averagePrice} minimum={group.minimumPrice} /></TableCell>
    <TableCell className="price-cell py-0">{formatPrice(group.currentPrice)}</TableCell>
    <TableCell className="price-cell py-0">{formatPrice(group.minimumPrice)}</TableCell>
    <TableCell className="price-cell py-0">{formatPrice(card?.averagePrice)}</TableCell>
    <TableCell className="py-0">{card ? <MarketplaceMark marketplace={card.marketplace} /> : '—'}</TableCell>
    <TableCell className="py-0"><AvailabilityStatus value={card?.currentAvailability ?? null} /></TableCell>
    <TableCell className="py-0">{edit}</TableCell>
  </TableRow>
})
