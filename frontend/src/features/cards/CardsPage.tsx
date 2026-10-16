import { Fragment, useCallback, useDeferredValue, useMemo, useState } from 'react'
import { ChevronDown, ChevronRight, FolderPlus, LayoutGrid, List, Pencil, Plus, RefreshCw, RotateCcw, Search } from 'lucide-react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useCards, useDeleteCard, useGroups, useUpdateCard } from '../../api/queries'
import { Button } from '../../components/ui/Button'
import { CardActionsMenu } from '../../components/ui/CardActionsMenu'
import { AvailabilityStatus } from '../../components/ui/AvailabilityStatus'
import { LoadingRows } from '../../components/ui/LoadingRows'
import { MarketplaceMark } from '../../components/ui/MarketplaceMark'
import { ProductImage } from '../../components/ui/ProductImage'
import { useCollection } from '../collection/CollectionProvider'
import type { MarketplaceCard, ProductGroup } from '../../types/domain'
import { formatDateTime, formatPrice, formatRelativeTime } from '../../utils/format'
import { AddCardDrawer } from './AddCardDrawer'
import { ImportExportControls } from './ImportExportControls'
import { GroupDialog } from './GroupDialog'

type Sort = 'default' | 'price-asc' | 'price-desc' | 'updated-desc'

function matchesStatus(card: MarketplaceCard, status: string) {
  if (status === 'all') return true
  if (status === 'excluded') return !card.isActive
  if (status === 'no_data') return card.lastObservedAt === null
  return card.currentAvailability === status
}

export function CardsPage() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editingGroup, setEditingGroup] = useState<ProductGroup | 'new' | null>(null)
  const [collapsedGroups, setCollapsedGroups] = useState<number[]>([])
  const [transferStatus, setTransferStatus] = useState<{ message: string; kind: 'success' | 'error' } | null>(null)
  const cardsQuery = useCards()
  const groupsQuery = useGroups()
  const updateCard = useUpdateCard()
  const deleteCard = useDeleteCard()
  const collection = useCollection()
  const query = params.get('q') ?? ''
  const deferredQuery = useDeferredValue(query.trim().toLowerCase())
  const marketplace = params.get('marketplace') ?? 'all'
  const rawStatus = params.get('status') ?? 'all'
  const status = rawStatus === 'archived' || rawStatus === 'paused' ? 'excluded' : rawStatus
  const sort = (params.get('sort') ?? 'default') as Sort
  const view = params.get('view') === 'grid' ? 'grid' : 'list'
  const hasFilters = Boolean(query || marketplace !== 'all' || status !== 'all' || sort !== 'default')
  const groupNames = useMemo(() => new Map((groupsQuery.data ?? []).map((group) => [group.id, group.name.toLowerCase()])), [groupsQuery.data])

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
      return (!deferredQuery || text.includes(deferredQuery) || groupNames.get(card.groupId ?? -1)?.includes(deferredQuery))
        && (marketplace === 'all' || card.marketplace === marketplace)
        && matchesStatus(card, status)
    })
    return result.toSorted((left, right) => {
      if (left.isActive !== right.isActive) return left.isActive ? -1 : 1
      if (sort === 'price-asc') return (left.currentPrice ?? Infinity) - (right.currentPrice ?? Infinity) || left.id - right.id
      if (sort === 'price-desc') return (right.currentPrice ?? -Infinity) - (left.currentPrice ?? -Infinity) || left.id - right.id
      if (sort === 'updated-desc') return (right.lastObservedAt ? Date.parse(right.updatedAt) : 0) - (left.lastObservedAt ? Date.parse(left.updatedAt) : 0) || left.id - right.id
      return left.id - right.id
    })
  }, [cardsQuery.data, deferredQuery, groupNames, marketplace, sort, status])

  const groupedCards = useMemo(() => {
    const byGroup = new Map<number, MarketplaceCard[]>()
    for (const card of visibleCards) {
      if (card.groupId === null || card.groupId === undefined) continue
      const members = byGroup.get(card.groupId) ?? []
      members.push(card)
      byGroup.set(card.groupId, members)
    }
    return byGroup
  }, [visibleCards])
  const visibleGroups = (groupsQuery.data ?? []).filter((group) =>
    groupedCards.has(group.id) || (!deferredQuery && marketplace === 'all' && status === 'all' && group.cardIds.length === 0))
  const standaloneCards = visibleCards.filter((card) => !groupedCards.has(card.groupId ?? -1))
  const orderedItems = [
    ...visibleGroups.map((group) => ({ kind: 'group' as const, group, active: (groupedCards.get(group.id) ?? []).some((card) => card.isActive) })),
    ...standaloneCards.map((card) => ({ kind: 'card' as const, card, active: card.isActive })),
  ].toSorted((left, right) => Number(right.active) - Number(left.active))

  function toggleGroup(groupId: number) {
    setCollapsedGroups((current) => current.includes(groupId) ? current.filter((id) => id !== groupId) : [...current, groupId])
  }

  function resetFilters() {
    setParams(view === 'grid' ? { view: 'grid' } : {}, { replace: true })
  }

  function actions(card: MarketplaceCard) {
    return <CardActionsMenu cardTitle={card.title ?? card.externalId} isActive={card.isActive}
      onRefresh={() => collection.start(card.id)} refreshDisabled={collection.isStarting}
      onToggle={() => updateCard.mutateAsync({ cardId: card.id, input: { isActive: !card.isActive } })}
      onDelete={() => deleteCard.mutateAsync(card.id)} />
  }

  function dealStatus(card: MarketplaceCard) {
    return <>
      {!card.isActive ? <span className="tracking-status">Не показывается в выгодных предложениях</span> : null}
    </>
  }

  function tile(card: MarketplaceCard) {
    return <li key={card.id} className="cards-grid__item">
      <div className="cards-grid__actions">{actions(card)}</div>
      <Link className="cards-grid__link" to={`/cards/${card.id}`}>
        <ProductImage card={card} large />
        <span className="cards-grid__title">{card.title ?? 'Без названия'}</span>
        <span className="cards-grid__id">ID: {card.externalId}</span>
      </Link>
      <div className="cards-grid__details"><MarketplaceMark marketplace={card.marketplace} /><strong className="price-cell">{formatPrice(card.currentPrice)}</strong></div>
      <div className="cards-grid__details"><time dateTime={card.lastObservedAt ? card.updatedAt : undefined} title={formatDateTime(card.lastObservedAt ? card.updatedAt : null)}>{formatRelativeTime(card.lastObservedAt ? card.updatedAt : null)}</time><AvailabilityStatus value={card.currentAvailability} /></div>
      {!card.isActive ? <div className="cards-grid__tracking">{dealStatus(card)}</div> : null}
    </li>
  }

  function row(card: MarketplaceCard, nested = false) {
    return <tr key={card.id} className={nested ? 'cards-table__nested' : ''} onClick={() => navigate(`/cards/${card.id}`)}>
      <td><div className="card-identity"><ProductImage card={card} /><span><strong>{card.title ?? 'Без названия'}</strong><small>ID: {card.externalId}</small>{dealStatus(card)}</span></div></td>
      <td><MarketplaceMark marketplace={card.marketplace} /></td>
      <td className="price-cell">{formatPrice(card.currentPrice)}</td>
      <td><AvailabilityStatus value={card.currentAvailability} /></td>
      <td><time dateTime={card.lastObservedAt ? card.updatedAt : undefined} title={formatDateTime(card.lastObservedAt ? card.updatedAt : null)}>{formatRelativeTime(card.lastObservedAt ? card.updatedAt : null)}</time></td>
      <td>{actions(card)}</td>
    </tr>
  }

  return (
    <section className="page cards-page">
      <header className="page-header">
        <div><h1>Карточки</h1><p>Текущие цены и история отслеживаемых карточек</p></div>
        <div className="page-actions">
          <ImportExportControls onStatus={(message, kind) => setTransferStatus({ message, kind })} />
          <Button icon={<FolderPlus />} onClick={() => setEditingGroup('new')}>Создать группу</Button>
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
            <option value="excluded">Не в выгодных предложениях</option>
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

      <div className="cards-view-bar">
        <span>{visibleCards.length} из {cardsQuery.data?.length ?? 0}</span>
        <div className="cards-view-switch" role="group" aria-label="Вид карточек">
          <button type="button" className={view === 'list' ? 'is-selected' : ''} aria-label="Список"
            aria-pressed={view === 'list'} title="Список" onClick={() => setParam('view', 'list', 'list')}><List aria-hidden="true" /></button>
          <button type="button" className={view === 'grid' ? 'is-selected' : ''} aria-label="Сетка"
            aria-pressed={view === 'grid'} title="Сетка" onClick={() => setParam('view', 'grid', 'list')}><LayoutGrid aria-hidden="true" /></button>
        </div>
      </div>

      <div className={view === 'list' || cardsQuery.isLoading || groupsQuery.isLoading || cardsQuery.isError || groupsQuery.isError || (visibleCards.length === 0 && visibleGroups.length === 0) ? 'table-surface' : ''}>
        {cardsQuery.isLoading || groupsQuery.isLoading ? <LoadingRows /> : cardsQuery.isError || groupsQuery.isError ? (
          <div className="state-message"><h2>Не удалось загрузить карточки</h2><p>Проверьте соединение с API и повторите.</p><Button onClick={() => { void cardsQuery.refetch(); void groupsQuery.refetch() }}>Повторить</Button></div>
        ) : visibleCards.length === 0 && visibleGroups.length === 0 ? (
          <div className="state-message"><h2>{hasFilters ? 'По выбранным условиям ничего не найдено' : 'Карточек пока нет'}</h2><p>{hasFilters ? 'Попробуйте изменить или сбросить фильтры.' : 'Добавьте первую карточку маркетплейса, чтобы начать собирать историю цены.'}</p><Button variant="primary" onClick={hasFilters ? resetFilters : () => setDrawerOpen(true)}>{hasFilters ? 'Сбросить фильтры' : 'Добавить карточку'}</Button></div>
        ) : view === 'grid' ? (
          <ul className="cards-grid" aria-label="Отслеживаемые карточки маркетплейсов">
            {orderedItems.map((item) => item.kind === 'group' ? <li key={`group-${item.group.id}`} className="cards-grid__group">
              <div className="product-group__header">
                <button type="button" className="product-group__toggle" aria-expanded={!collapsedGroups.includes(item.group.id)} onClick={() => toggleGroup(item.group.id)}>{collapsedGroups.includes(item.group.id) ? <ChevronRight /> : <ChevronDown />}<strong>{item.group.name}</strong><small>{item.group.cardIds.length} товаров</small></button>
                <span>Сейчас от {formatPrice(item.group.currentPrice)} · Минимум {formatPrice(item.group.minimumPrice)}</span>
                <Button variant="ghost" icon={<Pencil />} aria-label={`Изменить группу ${item.group.name}`} onClick={() => setEditingGroup(item.group)}>Изменить</Button>
              </div>
              {!collapsedGroups.includes(item.group.id) ? <ul className="cards-grid cards-grid--nested">{(groupedCards.get(item.group.id) ?? []).map(tile)}</ul> : null}
            </li> : tile(item.card))}
          </ul>
        ) : (
            <table className="cards-table">
              <caption className="sr-only">Отслеживаемые карточки маркетплейсов</caption>
              <thead><tr><th>Карточка</th><th>Маркетплейс</th><th>Цена</th><th>Наличие</th><th>Обновлено</th><th><span className="sr-only">Действия</span></th></tr></thead>
              <tbody>
                {orderedItems.map((item) => item.kind === 'group' ? <Fragment key={`group-${item.group.id}`}>
                  <tr className="cards-table__group"><td><button type="button" className="product-group__toggle" aria-expanded={!collapsedGroups.includes(item.group.id)} onClick={() => toggleGroup(item.group.id)}>{collapsedGroups.includes(item.group.id) ? <ChevronRight /> : <ChevronDown />}<strong>{item.group.name}</strong><small>{item.group.cardIds.length} товаров</small></button></td><td>Группа</td><td className="price-cell">{formatPrice(item.group.currentPrice)}<small className="product-group__minimum">Мин. за всё время: {formatPrice(item.group.minimumPrice)}</small></td><td /><td /><td><button type="button" className="product-group__edit" aria-label={`Изменить группу ${item.group.name}`} onClick={() => setEditingGroup(item.group)}><Pencil /></button></td></tr>
                  {!collapsedGroups.includes(item.group.id) ? (groupedCards.get(item.group.id) ?? []).map((card) => row(card, true)) : null}
                </Fragment> : row(item.card))}
              </tbody>
            </table>
        )}
      </div>
      <AddCardDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
      {editingGroup ? <GroupDialog key={editingGroup === 'new' ? 'new' : editingGroup.id} group={editingGroup === 'new' ? null : editingGroup} cards={cardsQuery.data ?? []} onClose={() => setEditingGroup(null)} /> : null}
    </section>
  )
}
