import { HelpHint } from '@/components/product/HelpHint'
import { midpointMoney, subtractMoney } from '../../utils/money'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyContent } from '@/components/ui/empty'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableCaption } from '@/components/ui/table'
import { Field, FieldLabel, FieldGroup } from '@/components/ui/field'
import { useState, type MouseEvent } from 'react'
import { ArrowLeft, ExternalLink, RefreshCw, Pencil } from 'lucide-react'
import { openUrl } from '@tauri-apps/plugin-opener'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ApiError, isDesktopMode } from '../../api/client'
import { useCard, useCardChart, useCardHistory, useCardVariants, useDeleteCard, useUpdateCard } from '../../api/queries'
import { AvailabilityStatus } from '../../components/product/AvailabilityStatus'
import { Button } from '../../components/ui/button'
import { CardActionsMenu } from '../../components/product/CardActionsMenu'
import { MarketplaceMark } from '../../components/product/MarketplaceMark'
import { PreparedProductImage } from '../../components/product/PreparedProductImage'
import { TagList } from '../../components/product/TagList'
import { formatDateTime, formatPrice, marketplaceLabel } from '../../utils/format'
import { useCollectionCommands } from '../collection/CollectionProvider'
import { VariantPriceChart } from './VariantPriceChart'
import { VariantPanel } from './VariantPanel'
import { CardDrawer } from '../cards/AddCardDrawer'
import { sortVariants, variantLabel } from './variantDisplay'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectGroup, SelectItem } from '@/components/ui/select'

const periods = [7, 30, 90] as const

export function CardDetailsPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const requestedReturn: unknown = location.state?.returnTo
  const returnTo = typeof requestedReturn === 'string' && /^\/cards(?:\?[^#]*)?$/.test(requestedReturn) ? requestedReturn : '/cards'
  const searchOptions = { state: location.state }
  const cardId = Number(useParams().cardId)
  const [params, setParams] = useSearchParams()
  const [editing, setEditing] = useState(false)
  const [historyVariantId, setHistoryVariantId] = useState<number | undefined>()
  const [openError, setOpenError] = useState<string | null>(null)
  const days = periods.includes(Number(params.get('days')) as 7 | 30 | 90) ? Number(params.get('days')) : 30
  const requestedPage = Number(params.get('page'))
  const page = Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1
  const cardQuery = useCard(cardId)
  const primaryVariantId = cardQuery.data?.primaryVariantId ?? undefined
  const historyQuery = useCardHistory(cardId, days, page, historyVariantId ?? primaryVariantId, !cardQuery.isPending)
  const mainHistoryQuery = useCardHistory(cardId, days, 1, primaryVariantId, !cardQuery.isPending)
  const variantsQuery = useCardVariants(cardId)
  const variants = variantsQuery.data ?? []
  const chartQuery = useCardChart(cardId, days)
  const updateCard = useUpdateCard()
  const deleteCard = useDeleteCard()
  const collection = useCollectionCommands()
  const card = cardQuery.data ?? historyQuery.data?.card
  const statistics = mainHistoryQuery.isError ? undefined : mainHistoryQuery.data?.statistics
  const history = historyQuery.data?.history ?? []
  const chart = chartQuery.data?.points ?? []
  const midpoint = statistics?.minimumPrice != null && statistics.maximumPrice != null
    ? midpointMoney(statistics.minimumPrice, statistics.maximumPrice) : null
  const priceGap = statistics?.minimumPrice != null && statistics.maximumPrice != null
    ? subtractMoney(statistics.maximumPrice, statistics.minimumPrice) : null

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

  if (cardQuery.isLoading && !card) return <section className="page detail-page"><Skeleton className="min-h-[560px]" aria-label="Загрузка карточки" /></section>
  if (cardQuery.error instanceof ApiError && cardQuery.error.code === 'card_not_found') {
    return <section className="page"><Empty><EmptyHeader><EmptyTitle>Товар не найден</EmptyTitle></EmptyHeader><EmptyContent><Link className="text-link" to={returnTo}>К товарам</Link></EmptyContent></Empty></section>
  }
  if (!card) {
    return (
      <section className="page">
        <Empty><EmptyHeader><EmptyTitle>Не удалось загрузить товар</EmptyTitle><EmptyDescription>Попробуйте ещё раз.</EmptyDescription></EmptyHeader><EmptyContent>
          <Button variant="outline" onClick={() => void Promise.all([cardQuery.refetch(), historyQuery.refetch(), chartQuery.refetch()])}>Повторить</Button>
          <Link className="text-link" to={returnTo}>К товарам</Link></EmptyContent>
        </Empty>
      </section>
    )
  }

  return (
    <section className="page detail-page">
      <Button asChild variant="outline" size="lg" className="mb-5 min-h-11 px-5"><Link to={returnTo}><ArrowLeft />К товарам</Link></Button>
      <header className="detail-header">
        <div className="detail-header__image"><PreparedProductImage profile="detail" card={card} alt={card.imageUrl ? `Фото товара: ${card.title ?? card.externalId}` : undefined} eager /></div>
        <div className="detail-header__info"><div className="detail-header__product">

          <div className="detail-header__content"><h1>{card.title ?? 'Без названия'}</h1><div className="detail-header__meta"><MarketplaceMark marketplace={card.marketplace} /><span>·</span><span>ID {card.externalId}</span><span>{Object.entries(card.options ?? {}).map(([name, value]) => `${name}: ${value}`).join(' · ')}</span>{!card.dealsEnabled ? <><span>·</span><Badge variant="warning" className="tracking-status">Исключён из выгодных</Badge></> : null}</div></div>
        </div>
        <div className="page-actions">
          <Button variant="outline" disabled={!variantsQuery.data} onClick={() => setEditing(true)}><Pencil data-icon="inline-start" aria-hidden="true" />Изменить</Button>
          {card.url ? <Button variant="outline" asChild><a href={card.url} target="_blank" rel="noopener noreferrer" onClick={(event) => void openProduct(event)}><ExternalLink data-icon="inline-start" aria-hidden="true" />Открыть на {marketplaceLabel[card.marketplace]}</a></Button> : null}
          <Button variant="outline" onClick={() => collection.start(card.id)} disabled={collection.isStarting}><RefreshCw data-icon="inline-start" />Обновить цены</Button>
          <CardActionsMenu bordered cardTitle={card.title ?? card.externalId} dealsEnabled={card.dealsEnabled} onToggle={() => updateCard.mutateAsync({ cardId: card.id, input: { dealsEnabled: !card.dealsEnabled } })} onDelete={async () => { await deleteCard.mutateAsync(card.id); navigate(returnTo, { replace: true }) }} />
        </div>

      <div className="price-summary"><HelpHint label="Статистика цен">Показатели главного варианта за выбранный период. Середина диапазона — (минимум + максимум) / 2. Разница — максимум − минимум.</HelpHint>
        <div className="price-summary__primary">
          <strong>{formatPrice(card.currentPrice)}</strong>
          <AvailabilityStatus value={card.currentAvailability} />
          <span>Обновлено: {formatDateTime(card.lastCollectedAt ?? null)}</span>
        </div>
        <div className="price-stat"><span>Минимум</span><strong>{formatPrice(statistics?.minimumPrice)}</strong></div>
        <div className="price-stat"><span>Середина диапазона</span><strong>{formatPrice(midpoint)}</strong></div>
        <div className="price-stat"><span>Максимум</span><strong>{formatPrice(statistics?.maximumPrice)}</strong></div>
        <div className="price-stat"><span>Разница</span><strong>{formatPrice(priceGap)}</strong></div>
      </div>
        {card.tags?.length ? <section className="detail-tags" aria-label="Теги товара"><TagList tags={card.tags} /></section> : null}
        </div>
      </header>
      {openError ? <Alert variant="destructive"><AlertDescription>{openError}</AlertDescription></Alert> : null}
      {collection.startError ? <Alert variant="destructive"><AlertDescription>{collection.startError}</AlertDescription></Alert> : null}
      {cardQuery.isError ? <SectionError message="Не удалось обновить товар" retry={() => void cardQuery.refetch()} /> : null}
      <CardDrawer open={editing} onClose={() => setEditing(false)} card={card} variants={variants} isPending={updateCard.isPending}
        onSave={({ title, url, tags, primaryVariantId }) => updateCard.mutateAsync({ cardId: card.id, input: { title, url, tags, primaryVariantId } })} />



      {variantsQuery.isError ? <SectionError message="Не удалось загрузить варианты" retry={() => void variantsQuery.refetch()} /> : variantsQuery.isLoading ? <Skeleton className="h-[160px]" aria-label="Загрузка вариантов" /> : <VariantPanel card={card} variants={variants} />}

      <div className="chart-heading">
        <h2>История цен</h2>
        <ToggleGroup type="single" value={String(days)} onValueChange={(value) => { if (value) setParams({ days: value }, searchOptions) }} variant="outline" spacing={0} aria-label="Период истории">
          {periods.map((period) => <ToggleGroupItem key={period} value={String(period)}>{period} дней</ToggleGroupItem>)}
        </ToggleGroup>
      </div>
      <section aria-label="История цен">{chartQuery.isLoading || variantsQuery.isLoading ? <Skeleton className="price-chart" aria-label="Загрузка графика" /> : chartQuery.isError ? <SectionError message="Не удалось загрузить график" retry={() => void chartQuery.refetch()} /> : <VariantPriceChart key={`${card.id}:${card.primaryVariantId}`} history={chart} variants={variants} primaryVariantId={card.primaryVariantId} />}</section>

      <section className="measurements">
        <div className="variant-heading"><h2>Измерения</h2>
          {variants.length > 1 ? <FieldGroup className="w-full sm:w-[320px]"><Field><FieldLabel htmlFor="history-variant">Вариант</FieldLabel>
            <Select value={historyVariantId === undefined ? 'primary' : String(historyVariantId)} onValueChange={(value) => { setHistoryVariantId(value === 'primary' ? undefined : Number(value)); setParams({ days: String(days) }, searchOptions) }}>
              <SelectTrigger id="history-variant"><SelectValue /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="primary">Главный вариант</SelectItem>{sortVariants(variants).map((v) => <SelectItem key={v.id} value={String(v.id)}>{variantLabel(v)}</SelectItem>)}</SelectGroup></SelectContent>
            </Select>
          </Field></FieldGroup> : null}
        </div>
        {historyQuery.isLoading ? <Skeleton className="h-[240px]" aria-label="Загрузка измерений" /> : historyQuery.isError ? <SectionError message="Не удалось загрузить измерения" retry={() => void historyQuery.refetch()} /> : <div className="table-surface">
          <Table className="history-table">
            <TableCaption className="sr-only">История измерений цены</TableCaption>
            <TableHeader><TableRow><TableHead>Дата и время</TableHead><TableHead>Цена</TableHead><TableHead>Наличие</TableHead></TableRow></TableHeader>
            <TableBody>{history.map((point) => <TableRow key={point.id}><TableCell>{formatDateTime(point.observedAt)}</TableCell><TableCell className="price-cell">{formatPrice(point.price)}</TableCell><TableCell><AvailabilityStatus value={point.availability} /></TableCell></TableRow>)}</TableBody>
          </Table>
          {history.length === 0 ? <Empty><EmptyHeader><EmptyTitle>Нет измерений за этот период</EmptyTitle></EmptyHeader></Empty> : null}
        </div>}
        {!historyQuery.isError && historyQuery.data && historyQuery.data.totalCount > historyQuery.data.pageSize ? (
          <div className="history-pagination">
            <Button disabled={page <= 1} onClick={() => setParams({ days: String(days), page: String(page - 1) }, searchOptions)}>Назад</Button>
            <span>Страница {page} из {Math.ceil(historyQuery.data.totalCount / historyQuery.data.pageSize)} · {historyQuery.data.totalCount} измерений</span>
            <Button disabled={page * historyQuery.data.pageSize >= historyQuery.data.totalCount} onClick={() => setParams({ days: String(days), page: String(page + 1) }, searchOptions)}>Далее</Button>
          </div>
        ) : null}
      </section>
    </section>
  )
}

function SectionError({ message, retry }: { message: string; retry: () => void }) {
  return <Alert variant="destructive" className="section-error"><AlertDescription>{message}<Button variant="outline" onClick={retry}>Повторить</Button></AlertDescription></Alert>
}
