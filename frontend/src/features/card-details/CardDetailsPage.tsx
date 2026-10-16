import { useState, type FormEvent, type MouseEvent } from 'react'
import { ArrowLeft, ExternalLink, RefreshCw } from 'lucide-react'
import { openUrl } from '@tauri-apps/plugin-opener'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ApiError, isDesktopMode } from '../../api/client'
import { useCard, useCardChart, useCardHistory, useDeleteCard, useUpdateCard } from '../../api/queries'
import { AvailabilityStatus } from '../../components/ui/AvailabilityStatus'
import { Button } from '../../components/ui/Button'
import { CardActionsMenu } from '../../components/ui/CardActionsMenu'
import { MarketplaceMark } from '../../components/ui/MarketplaceMark'
import { ProductImage } from '../../components/ui/ProductImage'
import { TagList } from '../../components/ui/TagList'
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
    <label className="field"><span>Теги товара</span><input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="Например, кухня, подарок" /><small>Не больше двух тегов, через запятую</small></label>
    <Button type="submit" disabled={updateCard.isPending}>Сохранить теги</Button>
    {error ? <span className="field__error" role="alert">{error}</span> : null}
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

  if (cardQuery.isLoading || historyQuery.isLoading || chartQuery.isLoading) return <section className="page detail-page"><div className="detail-loading" aria-label="Загрузка карточки" /></section>
  if (cardQuery.error instanceof ApiError && cardQuery.error.code === 'card_not_found') {
    return <section className="page"><div className="state-message"><h1>Карточка не найдена</h1><Link className="text-link" to="/cards">Вернуться к карточкам</Link></div></section>
  }
  if (!card || cardQuery.isError || historyQuery.isError || chartQuery.isError) {
    return (
      <section className="page">
        <div className="state-message">
          <h1>Не удалось загрузить данные карточки</h1>
          <p>Сервис временно не смог получить карточку или историю её цены.</p>
          <Button onClick={() => void Promise.all([cardQuery.refetch(), historyQuery.refetch(), chartQuery.refetch()])}>Повторить</Button>
          <Link className="text-link" to="/cards">Вернуться к карточкам</Link>
        </div>
      </section>
    )
  }

  return (
    <section className="page detail-page">
      <Link className="back-link" to="/cards"><ArrowLeft />К карточкам</Link>
      <header className="detail-header">
        <div className="detail-header__product">
          <ProductImage card={card} alt={card.imageUrl ? `Фото товара: ${card.title ?? card.externalId}` : undefined} eager />
          <div className="detail-header__content"><h1>{card.title ?? 'Без названия'}</h1><div className="detail-header__meta"><MarketplaceMark marketplace={card.marketplace} /><span>·</span><span>ID {card.externalId}</span>{!card.isActive ? <><span>·</span><span className="tracking-status">Не показывается в выгодных предложениях</span></> : null}</div></div>
        </div>
        <div className="page-actions">
          {card.url ? <a className="button button--secondary" href={card.url} target="_blank" rel="noopener noreferrer" onClick={(event) => void openProduct(event)}><ExternalLink aria-hidden="true" />Открыть на {marketplaceLabel[card.marketplace]}</a> : null}
          <Button icon={<RefreshCw />} onClick={() => collection.start(card.id)} disabled={collection.isStarting}>Обновить эту карточку</Button>
          <CardActionsMenu bordered cardTitle={card.title ?? card.externalId} isActive={card.isActive} onToggle={() => updateCard.mutateAsync({ cardId: card.id, input: { isActive: !card.isActive } })} onDelete={async () => { await deleteCard.mutateAsync(card.id); navigate('/cards', { replace: true }) }} />
        </div>
      </header>
      {openError ? <p className="action-error" role="alert">{openError}</p> : null}
      {collection.startError ? <p className="action-error" role="alert">{collection.startError}</p> : null}
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
        <div className="period-control" aria-label="Период истории">
          {periods.map((period) => <button key={period} className={days === period ? 'is-active' : ''} onClick={() => setParams({ days: String(period) })}>{period} дней</button>)}
        </div>
      </div>
      <PriceChart history={chart} midpoint={midpoint} />

      <section className="measurements">
        <h2>Измерения</h2>
        <div className="table-surface">
          <table className="history-table">
            <caption className="sr-only">История измерений цены</caption>
            <thead><tr><th>Дата и время</th><th>Цена</th><th>Наличие</th></tr></thead>
            <tbody>{history.map((point) => <tr key={point.id}><td>{formatDateTime(point.observedAt)}</td><td className="price-cell">{formatPrice(point.price)}</td><td><AvailabilityStatus value={point.availability} /></td></tr>)}</tbody>
          </table>
          {history.length === 0 ? <div className="state-message state-message--compact">Измерений за выбранный период нет</div> : null}
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
