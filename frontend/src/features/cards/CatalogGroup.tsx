import { memo } from 'react'
import { ChevronRight, ChevronDown, Pencil } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { TableRow, TableCell } from '@/components/ui/table'
import { ProductImage } from '../../components/product/ProductImage'
import { MarketplaceMark } from '../../components/product/MarketplaceMark'
import { AvailabilityStatus } from '../../components/product/AvailabilityStatus'
import { TagList } from '../../components/product/TagList'
import { dealStatus } from './CatalogProduct'
import { formatDateTime, formatPrice, formatRelativeTime } from '../../utils/format'
import type { ProductGroup } from '../../types/domain'
  function groupSaving(group: ProductGroup) {
    return group.savings !== null ? <span className="deal-savings">{formatPrice(group.savings)}</span> : 'Сейчас не выгодно'
  }

  function groupDetails(group: ProductGroup) {
    const card = group.representativeCard
    const updated = card?.lastObservedAt ? card.updatedAt : null
    return <div className="flex flex-wrap items-center gap-2">
      {card ? dealStatus(card) : null}
      {group.hasMemberDeals && !group.isDeal ? <Badge variant="secondary">Есть выгодный товар внутри</Badge> : null}
      <time dateTime={updated ?? undefined} title={formatDateTime(updated)}>{formatRelativeTime(updated)}</time>
    </div>
  }


interface Props {
 group: ProductGroup; view: 'list' | 'grid'; collapsed: boolean
 onToggle: (id: number) => void; onEdit: (group: ProductGroup) => void
 index: number; measure?: (element: HTMLTableRowElement | null) => void
}
export const CatalogGroup = memo(function CatalogGroup({group, view, collapsed, onToggle, onEdit, index, measure}: Props) {
 const card = group.representativeCard
 return view === 'grid' ? (<div className="product-group__header">
                <Button variant="ghost" type="button" className="product-group__toggle px-0" aria-expanded={!collapsed} onClick={() => onToggle(group.id)}>{collapsed ? <ChevronRight /> : <ChevronDown />}<strong>{group.name}</strong><small>{group.cardIds.length} товаров</small></Button><TagList tags={card?.tags} />
                <div className="flex flex-wrap items-center gap-3">
                  {card ? <><ProductImage card={card} /><MarketplaceMark marketplace={card.marketplace} /></> : null}
                  <span>Цена {formatPrice(card?.currentPrice)} · Минимальная {formatPrice(card?.minimumPrice)} · Средняя {formatPrice(card?.averagePrice)}</span>
                  {groupSaving(group)}<AvailabilityStatus value={card?.currentAvailability ?? null} />
                  {groupDetails(group)}
                </div>
                <Button variant="ghost" aria-label={`Изменить группу ${group.name}`} onClick={() => onEdit(group)}><Pencil data-icon="inline-start" />Изменить</Button>
              </div>) : (<TableRow data-index={index} data-vrow={index} aria-rowindex={index + 2} ref={measure} className="cards-table__group"><TableCell className="cards-table__selection py-0" /><TableCell className="py-0"><Button variant="ghost" type="button" className="product-group__toggle px-0" aria-expanded={!collapsed} onClick={() => onToggle(group.id)}>{collapsed ? <ChevronRight /> : <ChevronDown />}<strong>{group.name}</strong><small>{group.cardIds.length} товаров</small></Button><TagList tags={card?.tags} />{groupDetails(group)}</TableCell><TableCell className="py-0">{card ? <MarketplaceMark marketplace={card.marketplace} /> : '—'}</TableCell><TableCell className="price-cell py-0">{formatPrice(group.currentPrice)}</TableCell><TableCell className="price-cell py-0">{formatPrice(group.minimumPrice)}</TableCell><TableCell className="price-cell py-0">{formatPrice(card?.averagePrice)}</TableCell><TableCell className="py-0">{groupSaving(group)}</TableCell><TableCell className="py-0"><AvailabilityStatus value={card?.currentAvailability ?? null} /></TableCell><TableCell className="py-0"><Button variant="ghost" size="icon-sm" type="button" aria-label={`Изменить группу ${group.name}`} onClick={() => onEdit(group)}><Pencil /></Button></TableCell></TableRow>)
})
