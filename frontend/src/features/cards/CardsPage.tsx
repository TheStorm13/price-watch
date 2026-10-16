import { useCallback, useDeferredValue, useMemo, useState } from 'react'
import { Plus, RefreshCw, RotateCcw, Search } from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useCards, useDeleteCard, useUpdateCard } from '../../api/queries'
import { Button } from '../../components/ui/Button'
import { CardActionsMenu } from '../../components/ui/CardActionsMenu'
import { AvailabilityStatus } from '../../components/ui/AvailabilityStatus'
import { LoadingRows } from '../../components/ui/LoadingRows'
import { MarketplaceMark } from '../../components/ui/MarketplaceMark'
import { useCollection } from '../collection/CollectionProvider'
import type { Availability, Marketplace, MarketplaceCard } from '../../types/domain'
import { formatDateTime, formatPrice, formatRelativeTime } from '../../utils/format'
import { AddCardDrawer } from './AddCardDrawer'
import { ImportExportControls } from './ImportExportControls'

type Sort = 'default' | 'price-asc' | 'price-desc' | 'updated-desc'

function matchesStatus(card: MarketplaceCard, status: string) {
  if (status === 'all') return true
  if (status === 'no_data') return card.lastObservedAt === null
  return card.currentAvailability === status
}

export function CardsPage() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [transferStatus, setTransferStatus] = useState<{ message: string; kind: 'success' | 'error' } | null>(null)
  const cardsQuery = useCards()
  const updateCard = useUpdateCard()
  const deleteCard = useDeleteCard()
  const collection = useCollection()
  const query = params.get('q') ?? ''
  const deferredQuery = useDeferredValue(query.trim().toLowerCase())
  const marketplace = params.get('marketplace') ?? 'all'
  const status = params.get('status') ?? 'all'
  const sort = (params.get('sort') ?? 'default') as Sort
  const hasFilters = Boolean(query || marketplace !== 'all' || status !== 'all' || sort !== 'default')

  const setParam = useCallback((name: string, value: string, defaultValue = 'all') => {
    setParams((current) => {
      const next = new URLSearchParams(current)
      if (!value || value === defaultValue) next.delete(name)
      else next.set(name, value)
      return next
    }, { replace: true })
  }, [setParams])

  const visibleCards = useMemo(() => {
    const result = (cardsQuery.data ?? []).filter((card) => {
      const text = `${card.title ?? ''} ${card.externalId}`.toLowerCase()
      return (!deferredQuery || text.includes(deferredQuery))
        && (marketplace === 'all' || card.marketplace === marketplace)
        && matchesStatus(card, status)
    })
    return result.toSorted((left, right) => {
      if (sort === 'price-asc') return (left.currentPrice ?? Infinity) - (right.currentPrice ?? Infinity)
      if (sort === 'price-desc') return (right.currentPrice ?? -Infinity) - (left.currentPrice ?? -Infinity)
      if (sort === 'updated-desc') return (right.lastObservedAt ? Date.parse(right.updatedAt) : 0) - (left.lastObservedAt ? Date.parse(left.updatedAt) : 0)
      return Number(right.isActive) - Number(left.isActive) || left.id - right.id
    })
  }, [cardsQuery.data, deferredQuery, marketplace, sort, status])

  function resetFilters() {
    setParams({}, { replace: true })
  }

  return (
    <section className="page cards-page">
      <header className="page-header">
        <div><h1>Карточки</h1><p>Текущие цены и история отслеживаемых карточек</p></div>
        <div className="page-actions">
          <ImportExportControls onStatus={(message, kind) => setTransferStatus({ message, kind })} />
          <Button icon={<RefreshCw />} onClick={() => collection.start()} disabled={collection.isStarting}>Обновить цены</Button>
          <Button variant="primary" icon={<Plus />} onClick={() => setDrawerOpen(true)}>Добавить карточку</Button>
        </div>
      </header>
      {transferStatus ? <p className={`transfer-page-status transfer-page-status--${transferStatus.kind}`}
        role={transferStatus.kind === 'error' ? 'alert' : 'status'}>{transferStatus.message}</p> : null}
      {collection.startError ? <p className="action-error" role="alert">{collection.startError}</p> : null}

      <div className="filters">
        <label className="search-field">
          <Search aria-hidden="true" />
          <input value={query} onChange={(event) => setParam('q', event.target.value, '')} placeholder="Название или ID" aria-label="Поиск карточек" />
        </label>
        <div className="filters__selects">
          <select value={marketplace} onChange={(event) => setParam('marketplace', event.target.value)} aria-label="Маркетплейс">
            <option value="all">Все маркетплейсы</option>
            <option value="ozon">Ozon</option>
            <option value="wildberries">Wildberries</option>
            <option value="aliexpress">AliExpress</option>
          </select>
          <select value={status} onChange={(event) => setParam('status', event.target.value)} aria-label="Состояние">
            <option value="all">Все состояния</option>
            <option value="in_stock">В наличии</option>
            <option value="out_of_stock">Нет в наличии</option>
            <option value="no_data">Нет данных</option>
          </select>
          <select value={sort} onChange={(event) => setParam('sort', event.target.value, 'default')} aria-label="Сортировка">
            <option value="default">По умолчанию</option>
            <option value="price-asc">Сначала дешевле</option>
            <option value="price-desc">Сначала дороже</option>
            <option value="updated-desc">Недавно обновлённые</option>
          </select>
          {hasFilters ? <Button variant="ghost" icon={<RotateCcw />} onClick={resetFilters}>Сбросить</Button> : null}
        </div>
      </div>

      <div className="table-surface">
        {cardsQuery.isLoading ? <LoadingRows /> : cardsQuery.isError ? (
          <div className="state-message"><h2>Не удалось загрузить карточки</h2><p>Проверьте соединение с API и повторите.</p><Button onClick={() => cardsQuery.refetch()}>Повторить</Button></div>
        ) : visibleCards.length === 0 ? (
          <div className="state-message"><h2>{hasFilters ? 'По выбранным условиям ничего не найдено' : 'Карточек пока нет'}</h2><p>{hasFilters ? 'Попробуйте изменить или сбросить фильтры.' : 'Добавьте первую карточку маркетплейса, чтобы начать собирать историю цены.'}</p><Button variant="primary" onClick={hasFilters ? resetFilters : () => setDrawerOpen(true)}>{hasFilters ? 'Сбросить фильтры' : 'Добавить карточку'}</Button></div>
        ) : (
          <>
            <table className="cards-table">
              <caption className="sr-only">Отслеживаемые карточки маркетплейсов</caption>
              <thead><tr><th>Карточка</th><th>Маркетплейс</th><th>Цена</th><th>Наличие</th><th>Обновлено</th><th><span className="sr-only">Действия</span></th></tr></thead>
              <tbody>
                {visibleCards.map((card) => (
                  <tr key={card.id} className={!card.isActive ? 'is-inactive' : ''} onClick={() => navigate(`/cards/${card.id}`)}>
                    <td><div className="card-identity"><span className="product-placeholder" aria-hidden="true">{(card.title ?? 'Т').slice(0, 1)}</span><span><strong>{card.title ?? 'Без названия'}</strong><small>ID: {card.externalId}</small>{!card.isActive ? <span className="tracking-status">Отслеживание приостановлено</span> : null}</span></div></td>
                    <td><MarketplaceMark marketplace={card.marketplace} /></td>
                    <td className="price-cell">{formatPrice(card.currentPrice)}</td>
                    <td><AvailabilityStatus value={card.currentAvailability} /></td>
                    <td><time dateTime={card.lastObservedAt ? card.updatedAt : undefined} title={formatDateTime(card.lastObservedAt ? card.updatedAt : null)}>{formatRelativeTime(card.lastObservedAt ? card.updatedAt : null)}</time></td>
                    <td><CardActionsMenu cardTitle={card.title ?? card.externalId} isActive={card.isActive} onRefresh={() => collection.start(card.id)} refreshDisabled={collection.isStarting} onToggle={() => updateCard.mutateAsync({ cardId: card.id, input: { isActive: !card.isActive } })} onDelete={() => deleteCard.mutateAsync(card.id)} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
      <AddCardDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
    </section>
  )
}
