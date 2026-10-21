import { Alert, AlertDescription } from '@/components/ui/alert'
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyContent } from '@/components/ui/empty'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableCaption } from '@/components/ui/table'
import { Input } from '@/components/ui/input'
import { Field, FieldLabel, FieldDescription, FieldGroup } from '@/components/ui/field'
import { useState, type FormEvent, type MouseEvent } from 'react'
import { ArrowLeft, ExternalLink, RefreshCw } from 'lucide-react'
import { openUrl } from '@tauri-apps/plugin-opener'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ApiError, isDesktopMode } from '../../api/client'
import { useCard, useCardChart, useCardHistory, useDeleteCard, useUpdateCard } from '../../api/queries'
import { AvailabilityStatus } from '../../components/product/AvailabilityStatus'
import { Button } from '../../components/ui/button'
import { CardActionsMenu } from '../../components/product/CardActionsMenu'
import { MarketplaceMark } from '../../components/product/MarketplaceMark'
import { ProductImage } from '../../components/product/ProductImage'
import { TagList } from '../../components/product/TagList'
import { formatDateTime, formatPrice, marketplaceLabel } from '../../utils/format'
import { useCollection } from '../collection/CollectionProvider'
import { PriceChart } from './PriceChart'
import { parseTags } from '../cards/tags'

const periods = [7, 30, 90] as const

function CardTagsEditor({ card }: { card: NonNullable<ReturnType<typeof useCard>['data']> }) {
  const [tags, setTags] = useState((card.tags ?? []).join(', '))
  const [error, setError] = useState<string | null>(null)
  const updateCard = useUpdateCard()

  async function save(event: FormEvent) {
    event.preventDefault()
    try {
      const parsed = parseTags(tags, 2)
      await updateCard.mutateAsync({ cardId: card.id, input: { tags: parsed } })
      setTags(parsed.join(', '))
      setError(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Не удалось сохранить теги')
    }
  }

  return <form className="detail-tags" onSubmit={(event) => void save(event)}>
    <FieldGroup className="max-w-[360px]"><Field data-invalid={Boolean(error)}><FieldLabel htmlFor="field-carddetailspage-1">Теги товара</FieldLabel><Input id="field-carddetailspage-1" aria-invalid={Boolean(error)} value={tags} onChange={(event) => setTags(event.target.value)} placeholder="Например, кухня, подарок" /><FieldDescription>Не больше двух тегов, через запятую</FieldDescription></Field></FieldGroup>
    <Button variant="outline" type="submit" disabled={updateCard.isPending}>Сохранить теги</Button>
    {error ? <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert> : null}
  </form>
}

export function CardDetailsPage() {
  const navigate = useNavigate()
  const cardId = Number(useParams().cardId)
  const [params, setParams] = useSearchParams()
  const [openError, setOpenError] = useState<string | null>(null)
  const days = periods.includes(Number(params.get('days')) as 7 | 30 | 90) ? Number(params.get('days')) : 30
  const requestedPage = Number(params.get('page'))
  const page = Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1
  const cardQuery = useCard(cardId)
  const historyQuery = useCardHistory(cardId, days, page)
  const chartQuery = useCardChart(cardId, days)
  const updateCard = useUpdateCard()
  const deleteCard = useDeleteCard()
  const collection = useCollection()
  const card = cardQuery.data ?? historyQuery.data?.card
  const statistics = historyQuery.data?.statistics
  const history = historyQuery.data?.history ?? []
  const chart = chartQuery.data?.points ?? []
  const midpoint = statistics?.minimumPrice != null && statistics.maximumPrice != null
    ? (statistics.minimumPrice + statistics.maximumPrice) / 2 : null
  const priceGap = statistics?.minimumPrice != null && statistics.maximumPrice != null
    ? statistics.maximumPrice - statistics.minimumPrice : null

  async function openProduct(event: MouseEvent<HTMLAnchorElement>) {
    if (!isDesktopMode || !card?.url) return
    event.preventDefault()
    setOpenError(null)
    try {
      await openUrl(card.url)
    } catch {
      setOpenError('Не удалось открыть страницу товара в браузере')
    }
  }

  if (cardQuery.isLoading || historyQuery.isLoading || chartQuery.isLoading) return <section className="page detail-page"><Skeleton className="min-h-[560px]" aria-label="Загрузка карточки" /></section>
  if (cardQuery.error instanceof ApiError && cardQuery.error.code === 'card_not_found') {
    return <section className="page"><Empty><EmptyHeader><EmptyTitle>Карточка не найдена</EmptyTitle></EmptyHeader><EmptyContent><Link className="text-link" to="/cards">Вернуться к карточкам</Link></EmptyContent></Empty></section>
  }
  if (!card || cardQuery.isError || historyQuery.isError || chartQuery.isError) {
    return (
      <section className="page">
        <Empty><EmptyHeader><EmptyTitle>Не удалось загрузить данные карточки</EmptyTitle><EmptyDescription>Сервис временно не смог получить карточку или историю её цены.</EmptyDescription></EmptyHeader><EmptyContent>
          <Button variant="outline" onClick={() => void Promise.all([cardQuery.refetch(), historyQuery.refetch(), chartQuery.refetch()])}>Повторить</Button>
          <Link className="text-link" to="/cards">Вернуться к карточкам</Link></EmptyContent>
        </Empty>
      </section>
    )
  }

  return (
    <section className="page detail-page">
      <Link className="back-link" to="/cards"><ArrowLeft />К карточкам</Link>
      <header className="detail-header">
        <div className="detail-header__product">
          <ProductImage card={card} alt={card.imageUrl ? `Фото товара: ${card.title ?? card.externalId}` : undefined} eager />
          <div className="detail-header__content"><h1>{card.title ?? 'Без названия'}</h1><div className="detail-header__meta"><MarketplaceMark marketplace={card.marketplace} /><span>·</span><span>ID {card.externalId}</span>{!card.dealsEnabled ? <><span>·</span><Badge variant="warning" className="tracking-status">Не участвует в выгодных</Badge></> : null}</div></div>
        </div>
        <div className="page-actions">
          {card.url ? <Button variant="outline" asChild><a href={card.url} target="_blank" rel="noopener noreferrer" onClick={(event) => void openProduct(event)}><ExternalLink data-icon="inline-start" aria-hidden="true" />Открыть на {marketplaceLabel[card.marketplace]}</a></Button> : null}
          {card.marketplace === 'ozon'
            ? <Button variant="outline" onClick={() => collection.start(card.id)} disabled={collection.isStarting}><RefreshCw data-icon="inline-start" />Обновить эту карточку</Button>
            : <Badge variant="warning" className="tracking-status">Сбор цен пока недоступен: коннектор не подключён</Badge>}
          <CardActionsMenu bordered cardTitle={card.title ?? card.externalId} dealsEnabled={card.dealsEnabled} onToggle={() => updateCard.mutateAsync({ cardId: card.id, input: { dealsEnabled: !card.dealsEnabled } })} onDelete={async () => { await deleteCard.mutateAsync(card.id); navigate('/cards', { replace: true }) }} />
        </div>
      </header>
      {openError ? <Alert variant="destructive"><AlertDescription>{openError}</AlertDescription></Alert> : null}
      {collection.startError ? <Alert variant="destructive"><AlertDescription>{collection.startError}</AlertDescription></Alert> : null}
      <TagList tags={card.tags} />
      <CardTagsEditor key={card.id} card={card} />

      <div className="price-summary">
        <div className="price-summary__primary">
          <strong>{formatPrice(card.currentPrice)}</strong>
          <AvailabilityStatus value={card.currentAvailability} />
          <span>Обновлено: {formatDateTime(card.lastObservedAt ? card.updatedAt : null)}</span>
        </div>
        <div className="price-stat"><span>Минимум</span><strong>{formatPrice(statistics?.minimumPrice)}</strong></div>
        <div className="price-stat"><span>Середина диапазона</span><strong>{formatPrice(midpoint)}</strong></div>
        <div className="price-stat"><span>Максимум</span><strong>{formatPrice(statistics?.maximumPrice)}</strong></div>
        <div className="price-stat"><span>Разница</span><strong>{formatPrice(priceGap)}</strong></div>
      </div>

      <div className="chart-heading">
        <h2>История цены</h2>
        <ToggleGroup type="single" value={String(days)} onValueChange={(value) => { if (value) setParams({ days: value }) }} variant="outline" spacing={0} aria-label="Период истории">
          {periods.map((period) => <ToggleGroupItem key={period} value={String(period)}>{period} дней</ToggleGroupItem>)}
        </ToggleGroup>
      </div>
      <PriceChart history={chart} midpoint={midpoint} />

      <section className="measurements">
        <h2>Измерения</h2>
        <div className="table-surface">
          <Table className="history-table">
            <TableCaption className="sr-only">История измерений цены</TableCaption>
            <TableHeader><TableRow><TableHead>Дата и время</TableHead><TableHead>Цена</TableHead><TableHead>Наличие</TableHead></TableRow></TableHeader>
            <TableBody>{history.map((point) => <TableRow key={point.id}><TableCell>{formatDateTime(point.observedAt)}</TableCell><TableCell className="price-cell">{formatPrice(point.price)}</TableCell><TableCell><AvailabilityStatus value={point.availability} /></TableCell></TableRow>)}</TableBody>
          </Table>
          {history.length === 0 ? <Empty><EmptyHeader><EmptyTitle>Измерений за выбранный период нет</EmptyTitle></EmptyHeader></Empty> : null}
        </div>
        {historyQuery.data && historyQuery.data.totalCount > historyQuery.data.pageSize ? (
          <div className="history-pagination">
            <Button disabled={page <= 1} onClick={() => setParams({ days: String(days), page: String(page - 1) })}>Назад</Button>
            <span>Страница {page} из {Math.ceil(historyQuery.data.totalCount / historyQuery.data.pageSize)} · {historyQuery.data.totalCount} измерений</span>
            <Button disabled={page * historyQuery.data.pageSize >= historyQuery.data.totalCount} onClick={() => setParams({ days: String(days), page: String(page + 1) })}>Далее</Button>
          </div>
        ) : null}
      </section>
    </section>
  )
}
