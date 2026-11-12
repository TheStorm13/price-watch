import { memo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { TableRow, TableCell } from '@/components/ui/table'
import { useDeleteCard, useUpdateCard } from '../../api/queries'
import { CardActionsMenu } from '../../components/product/CardActionsMenu'
import { AvailabilityStatus } from '../../components/product/AvailabilityStatus'
import { MarketplaceMark } from '../../components/product/MarketplaceMark'
import { PreparedProductImage } from '../../components/product/PreparedProductImage'
import { TagList } from '../../components/product/TagList'
import { useCollectionCommands } from '../collection/CollectionProvider'
import type { TrackedCardView } from '../../types/domain'
import { formatDateTime, formatPrice, formatRelativeTime } from '../../utils/format'
import type { DecimalString } from '../../utils/money'
import { catalogSavings } from './catalogSavings'
import { CatalogSavings } from './CatalogSavings'

export function dealStatus(card: TrackedCardView) {
    return <>
      {!card.dealsEnabled ? <Badge variant="warning" className="tracking-status" title="Исключён из выгодных">Исключён из выгодных</Badge> : null}
    </>
  }

interface Props {
  card: TrackedCardView; view: 'list' | 'grid'; nested?: boolean; selected: boolean
  savings: DecimalString | null; returnTo: string; onToggle: (id: number) => void
  index: number; blockEnd: boolean; measure?: (element: HTMLTableRowElement | null) => void
}
export const CatalogProduct = memo(function CatalogProduct({ card, view, nested = false, selected, savings, returnTo, onToggle, index, blockEnd, measure }: Props) {
  const navigate = useNavigate()
  const cardLocationState = { returnTo }
  const updateCard = useUpdateCard(), deleteCard = useDeleteCard()
  const collection = useCollectionCommands()
  function actions(card: TrackedCardView) {
    return <CardActionsMenu cardTitle={card.title ?? card.externalId} dealsEnabled={card.dealsEnabled}
      onRefresh={() => collection.start(card.id)} refreshDisabled={collection.isStarting}
      onToggle={() => updateCard.mutateAsync({ cardId: card.id, input: { dealsEnabled: !card.dealsEnabled } })}
      onDelete={() => deleteCard.mutateAsync(card.id)} />
  }

  function tile(card: TrackedCardView) {
    return <Card key={card.id} asChild className="grid gap-0 py-0"><li className={cn("cards-grid__item", selected && "is-selected")}>
      <div className="cards-grid__selection"><Checkbox aria-label={`Выбрать карточку ${card.title ?? 'Без названия'}`} checked={selected} onCheckedChange={() => onToggle(card.id)} /></div>
      <div className="cards-grid__actions">{actions(card)}</div>
      <CardHeader className="contents"><Link className="cards-grid__link" to={`/cards/${card.id}`} state={cardLocationState}>
        <span className="cards-grid__media"><PreparedProductImage card={card} profile="tile" /></span>
        <CardTitle className="contents"><span className="cards-grid__title" title={card.title ?? 'Без названия'}>{card.title ?? 'Без названия'}</span></CardTitle>
        {Object.keys(card.options ?? {}).length ? <span className="text-sm text-muted-foreground">{Object.values(card.options ?? {}).join(' · ')}</span> : null}
      </Link></CardHeader>
      <CardContent className="contents"><div className="cards-grid__tags" title={card.tags?.join(', ')}><TagList tags={card.tags} /></div>
      <div className="cards-grid__details"><MarketplaceMark marketplace={card.marketplace} /></div>
      <dl className="cards-grid__prices"><div><dt>Выгода / макс.</dt><dd><CatalogSavings assessment={card.purchaseAssessment} observedAt={card.lastObservedAt} savings={catalogSavings(card, savings)} average={card.averagePrice} minimum={card.minimumPrice} /></dd></div><div><dt>Цена</dt><dd>{formatPrice(card.currentPrice)}</dd></div><div><dt>Минимальная</dt><dd>{formatPrice(card.minimumPrice)}</dd></div><div><dt>Средняя</dt><dd>{formatPrice(card.averagePrice)}</dd></div></dl>
      </CardContent><CardFooter className="contents"><div className="cards-grid__details"><time dateTime={card.lastCollectedAt ?? undefined} title={formatDateTime(card.lastCollectedAt ?? null)}>{formatRelativeTime(card.lastCollectedAt ?? null)}</time><AvailabilityStatus value={card.currentAvailability} /></div>
      <div className="cards-grid__tracking">{dealStatus(card)}</div>
    </CardFooter></li></Card>
  }

  function row(card: TrackedCardView, nested = false) {
    return <TableRow data-index={index} data-vrow={index} data-block-start={!nested || undefined} data-block-end={blockEnd || undefined} ref={measure} aria-rowindex={index + 2} key={card.id} className={cn('cards-table__product', nested && 'cards-table__nested', selected && 'is-selected')} onClick={(event) => { if (!(event.target as HTMLElement).closest('a, button, input, [role="checkbox"]')) navigate(`/cards/${card.id}`, { state: cardLocationState }) }}>
      <TableCell className="cards-table__selection py-1"><Checkbox aria-label={`Выбрать карточку ${card.title ?? card.externalId}`}
        checked={selected} onClick={(event) => event.stopPropagation()} onCheckedChange={() => onToggle(card.id)} /></TableCell>
      <TableCell className="py-1"><div className="card-identity"><PreparedProductImage card={card} /><span><Link to={`/cards/${card.id}`} state={cardLocationState} className="card-identity__link"><strong title={card.title ?? 'Без названия'}>{card.title ?? 'Без названия'}</strong></Link>{Object.keys(card.options ?? {}).length ? <span className="text-sm text-muted-foreground">{Object.values(card.options ?? {}).join(' · ')}</span> : null}<TagList tags={card.tags} />{dealStatus(card)}</span></div></TableCell>
      <TableCell className="py-1"><CatalogSavings assessment={card.purchaseAssessment} observedAt={card.lastObservedAt} savings={catalogSavings(card, savings)} average={card.averagePrice} minimum={card.minimumPrice} /></TableCell>
      <TableCell className="price-cell py-1">{formatPrice(card.currentPrice)}</TableCell>
      <TableCell className="price-cell py-1">{formatPrice(card.minimumPrice)}</TableCell>
      <TableCell className="price-cell py-1">{formatPrice(card.averagePrice)}</TableCell>
      <TableCell className="py-1"><MarketplaceMark marketplace={card.marketplace} /></TableCell>
      <TableCell className="py-1"><AvailabilityStatus value={card.currentAvailability} /></TableCell>
      <TableCell className="py-1">{actions(card)}</TableCell>
    </TableRow>
  }

  return view === 'grid' ? tile(card) : row(card, nested)
})
