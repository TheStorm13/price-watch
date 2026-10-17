import { Fragment, useCallback, useDeferredValue, useMemo, useState } from 'react'
import { ArrowDown, ArrowUp, ChevronDown, ChevronRight, FolderPlus, LayoutGrid, List, Pencil, Plus, RefreshCw, RotateCcw, Search } from 'lucide-react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useCards, useDeals, useDeleteCard, useGroups, useUpdateCard } from '../../api/queries'
import { Button } from '../../components/ui/Button'
import { CardActionsMenu } from '../../components/ui/CardActionsMenu'
import { AvailabilityStatus } from '../../components/ui/AvailabilityStatus'
import { LoadingRows } from '../../components/ui/LoadingRows'
import { MarketplaceMark } from '../../components/ui/MarketplaceMark'
import { ProductImage } from '../../components/ui/ProductImage'
import { TagList } from '../../components/ui/TagList'
import { useCollection } from '../collection/CollectionProvider'
import type { MarketplaceCard, ProductGroup } from '../../types/domain'
import { availabilityLabel, formatDateTime, formatPrice, formatRelativeTime, marketplaceLabel } from '../../utils/format'
import { AddCardDrawer } from './AddCardDrawer'
import { ImportExportControls } from './ImportExportControls'
import { GroupDialog } from './GroupDialog'

const columnSortKeys = ['title', 'marketplace', 'price', 'minimum', 'average', 'savings', 'availability'] as const
type ColumnSortKey = typeof columnSortKeys[number]
type SortKey = ColumnSortKey | 'updated'
type Sort = { key: SortKey; direction: 'asc' | 'desc' } | null
type DisplayItem = { kind: 'card'; card: MarketplaceCard; dealsEnabled: boolean } | { kind: 'group'; group: ProductGroup; dealsEnabled: boolean }
const collator = new Intl.Collator('ru', { numeric: true, sensitivity: 'base' })
const columnLabels: Record<ColumnSortKey, string> = {
  title: 'Карточка', marketplace: 'Маркетплейс', price: 'Цена', minimum: 'Минимальная',
  average: 'Средняя', savings: 'Выгода', availability: 'Наличие',
}

function parseSort(value: string | null): Sort {
  if (!value) return null
  const parts = value.split('-')
  if (parts.length !== 2) return null
  const [key, direction] = parts
  const validColumn = columnSortKeys.includes(key as ColumnSortKey) && (direction === 'asc' || direction === 'desc')
  return (validColumn || key === 'updated' && direction === 'desc')
    ? { key: key as SortKey, direction }
    : null
}

function sortValue(item: DisplayItem, key: SortKey, savings: Map<number, number>): string | number | null {
  if (item.kind === 'group') {
    if (key === 'title') return item.group.name
    if (key === 'marketplace') return 'Группа'
    if (key === 'price') return item.group.currentPrice
    if (key === 'minimum') return item.group.minimumPrice
    return null
  }
  const card = item.card
  if (key === 'title') return card.title ?? card.externalId
  if (key === 'marketplace') return marketplaceLabel[card.marketplace]
  if (key === 'price') return card.currentPrice
  if (key === 'minimum') return card.minimumPrice ?? null
  if (key === 'average') return card.averagePrice ?? null
  if (key === 'savings') return savings.get(card.id) ?? null
  if (key === 'updated') return card.lastObservedAt ? Date.parse(card.updatedAt) : null
  return card.currentAvailability ? availabilityLabel[card.currentAvailability] : null
}

function compareItems(left: DisplayItem, right: DisplayItem, sort: Sort, savings: Map<number, number>): number {
  if (left.dealsEnabled !== right.dealsEnabled) return left.dealsEnabled ? -1 : 1
  if (!sort) return left.kind === 'card' && right.kind === 'card' ? left.card.id - right.card.id : 0
  const first = sortValue(left, sort.key, savings)
  const second = sortValue(right, sort.key, savings)
  if (first === null || second === null) return first === null ? (second === null ? 0 : 1) : -1
  const order = typeof first === 'number' && typeof second === 'number'
    ? first - second
    : collator.compare(String(first), String(second))
  return sort.direction === 'asc' ? order : -order
}

function matchesStatus(card: MarketplaceCard, status: string) {
  if (status === 'all') return true
  if (status === 'deals_disabled') return !card.dealsEnabled
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
  const dealsQuery = useDeals()
  const updateCard = useUpdateCard()
  const deleteCard = useDeleteCard()
  const collection = useCollection()
  const query = params.get('q') ?? ''
  const deferredQuery = useDeferredValue(query.trim().toLowerCase())
  const marketplace = params.get('marketplace') ?? 'all'
  const status = params.get('status') ?? 'all'
  const sortParam = params.get('sort')
  const sort = useMemo(() => parseSort(sortParam), [sortParam])
  const view = params.get('view') === 'grid' ? 'grid' : 'list'
  const dealsOnly = params.get('deals') === '1'
  const selectedTag = params.get('tag') ?? ''
  const hasFilters = Boolean(query || marketplace !== 'all' || status !== 'all' || sort || dealsOnly || selectedTag)
  const deals = useMemo(() => new Map((dealsQuery.data ?? []).map((deal) => [deal.card.id, deal])), [dealsQuery.data])
  const savings = useMemo(() => new Map((dealsQuery.data ?? []).map((deal) => [deal.card.id, deal.savings])), [dealsQuery.data])
  const groupNames = useMemo(() => new Map((groupsQuery.data ?? []).map((group) => [group.id, group.name.toLowerCase()])), [groupsQuery.data])
  const groupTags = useMemo(() => new Map((groupsQuery.data ?? []).map((group) => [group.id, group.tags ?? []])), [groupsQuery.data])
  const availableTags = useMemo(() => [...new Set([
    ...(cardsQuery.data ?? []).flatMap((card) => card.tags ?? []),
    ...(groupsQuery.data ?? []).flatMap((group) => group.tags ?? []),
  ])].sort(collator.compare), [cardsQuery.data, groupsQuery.data])

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
        && (!selectedTag || (card.tags ?? []).includes(selectedTag) || (groupTags.get(card.groupId ?? -1) ?? []).includes(selectedTag))
        && (!dealsOnly || deals.has(card.id))
    })
    return result.toSorted((left, right) => compareItems(
      { kind: 'card', card: left, dealsEnabled: left.dealsEnabled },
      { kind: 'card', card: right, dealsEnabled: right.dealsEnabled }, sort, savings))
  }, [cardsQuery.data, deals, dealsOnly, deferredQuery, groupNames, groupTags, marketplace, savings, selectedTag, sort, status])

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
    groupedCards.has(group.id) || (!dealsOnly && !deferredQuery && marketplace === 'all' && status === 'all' && group.cardIds.length === 0 && (!selectedTag || (group.tags ?? []).includes(selectedTag))))
  const standaloneCards = visibleCards.filter((card) => !groupedCards.has(card.groupId ?? -1))
  const orderedItems = [
    ...visibleGroups.map((group) => ({ kind: 'group' as const, group, dealsEnabled: (groupedCards.get(group.id) ?? []).some((card) => card.dealsEnabled) })),
    ...standaloneCards.map((card) => ({ kind: 'card' as const, card, dealsEnabled: card.dealsEnabled })),
  ].toSorted((left, right) => compareItems(left, right, sort, savings))
  const gridItems = [...orderedItems.filter((item) => item.kind === 'group'), ...orderedItems.filter((item) => item.kind === 'card')]

  function toggleSort(key: ColumnSortKey) {
    const next = sort?.key === key ? (sort.direction === 'asc' ? `${key}-desc` : '') : `${key}-asc`
    setParam('sort', next, '')
  }

  function sortableHeader(label: string, key: ColumnSortKey) {
    const direction = sort?.key === key ? sort.direction : null
    return <th scope="col" aria-sort={direction === 'asc' ? 'ascending' : direction === 'desc' ? 'descending' : 'none'}>
      <button type="button" className={`cards-table__sort${direction ? ' is-active' : ''}`} onClick={() => toggleSort(key)}
        title={direction === 'asc' ? 'Сортировать по убыванию' : direction === 'desc' ? 'Сбросить сортировку' : 'Сортировать по возрастанию'}>
        {label}<span className="cards-table__sort-icon" aria-hidden="true">{direction === 'desc' ? <ArrowDown /> : <ArrowUp />}</span>
      </button>
    </th>
  }

  function toggleGroup(groupId: number) {
    setCollapsedGroups((current) => current.includes(groupId) ? current.filter((id) => id !== groupId) : [...current, groupId])
  }

  function resetFilters() {
    setParams(view === 'grid' ? { view: 'grid' } : {}, { replace: true })
  }

  function actions(card: MarketplaceCard) {
    return <CardActionsMenu cardTitle={card.title ?? card.externalId} dealsEnabled={card.dealsEnabled}
      onRefresh={card.marketplace === 'ozon' ? () => collection.start(card.id) : undefined} refreshDisabled={collection.isStarting}
      onToggle={() => updateCard.mutateAsync({ cardId: card.id, input: { dealsEnabled: !card.dealsEnabled } })}
      onDelete={() => deleteCard.mutateAsync(card.id)} />
  }

  function dealStatus(card: MarketplaceCard) {
    return <>
      {!card.dealsEnabled ? <span className="tracking-status">Не учитывается в выгодных предложениях</span> : null}
    </>
  }

  function saving(card: MarketplaceCard) {
    const deal = deals.get(card.id)
    return deal ? <span className="deal-savings">{formatPrice(deal.savings)}</span> : 'Сейчас не выгодно'
  }

  function tile(card: MarketplaceCard) {
    return <li key={card.id} className="cards-grid__item">
      <div className="cards-grid__actions">{actions(card)}</div>
      <Link className="cards-grid__link" to={`/cards/${card.id}`}>
        <ProductImage card={card} large />
        <span className="cards-grid__title">{card.title ?? 'Без названия'}</span>
        <span className="cards-grid__id">ID: {card.externalId}</span>
      </Link>
      <TagList tags={card.tags} />
      <div className="cards-grid__details"><MarketplaceMark marketplace={card.marketplace} /></div>
      <dl className="cards-grid__prices"><div><dt>Цена</dt><dd>{formatPrice(card.currentPrice)}</dd></div><div><dt>Минимальная</dt><dd>{formatPrice(card.minimumPrice)}</dd></div><div><dt>Средняя</dt><dd>{formatPrice(card.averagePrice)}</dd></div><div><dt>Выгода</dt><dd>{saving(card)}</dd></div></dl>
      <div className="cards-grid__details"><time dateTime={card.lastObservedAt ? card.updatedAt : undefined} title={formatDateTime(card.lastObservedAt ? card.updatedAt : null)}>{formatRelativeTime(card.lastObservedAt ? card.updatedAt : null)}</time><AvailabilityStatus value={card.currentAvailability} /></div>
      {!card.dealsEnabled ? <div className="cards-grid__tracking">{dealStatus(card)}</div> : null}
    </li>
  }

  function row(card: MarketplaceCard, nested = false) {
    return <tr key={card.id} className={nested ? 'cards-table__nested' : ''} onClick={() => navigate(`/cards/${card.id}`)}>
      <td><div className="card-identity"><ProductImage card={card} /><span><strong>{card.title ?? 'Без названия'}</strong><small>ID: {card.externalId}</small><TagList tags={card.tags} />{dealStatus(card)}</span></div></td>
      <td><MarketplaceMark marketplace={card.marketplace} /></td>
      <td className="price-cell">{formatPrice(card.currentPrice)}</td>
      <td className="price-cell">{formatPrice(card.minimumPrice)}</td>
      <td className="price-cell">{formatPrice(card.averagePrice)}</td>
      <td>{saving(card)}</td>
      <td><AvailabilityStatus value={card.currentAvailability} /></td>
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
      {dealsQuery.isError && !dealsOnly ? <p className="action-error" role="alert">Не удалось загрузить данные о выгоде. <button type="button" onClick={() => void dealsQuery.refetch()}>Повторить</button></p> : null}

      <div className="filters">
        <label className="search-field">
          <Search aria-hidden="true" />
          <input value={query} onChange={(event) => setParam('q', event.target.value, '')} placeholder="Название или ID" aria-label="Поиск карточек" />
        </label>
        <div className="filters__selects">
          <span className={`filter-select${marketplace !== 'all' ? ' filter-select--active' : ''}`}>
            <select value={marketplace} onChange={(event) => setParam('marketplace', event.target.value)} aria-label="Маркетплейс">
              <option value="all">Все маркетплейсы</option>
              <option value="ozon">Ozon</option>
              <option value="wildberries">Wildberries</option>
              <option value="aliexpress">AliExpress</option>
              <option value="yandex-market">Яндекс Маркет</option>
            </select>
            <ChevronDown aria-hidden="true" />
          </span>
          <span className={`filter-select filter-select--status${status !== 'all' ? ' filter-select--active' : ''}`}>
            <select value={status} onChange={(event) => setParam('status', event.target.value)} aria-label="Состояние">
              <option value="all">Все состояния</option>
              <option value="in_stock">В наличии</option>
              <option value="out_of_stock">Нет в наличии</option>
              <option value="no_data">Нет данных</option>
              <option value="deals_disabled">Не учитывается в выгодных предложениях</option>
            </select>
            <ChevronDown aria-hidden="true" />
          </span>
          <span className={`filter-select filter-select--sort${sort ? ' filter-select--active' : ''}`}>
            <select value={sort ? `${sort.key}-${sort.direction}` : 'default'} onChange={(event) => setParam('sort', event.target.value, 'default')} aria-label="Сортировка">
              <option value="default">По умолчанию</option>
              <option value="price-asc">Сначала дешевле</option>
              <option value="price-desc">Сначала дороже</option>
              <option value="updated-desc">Недавно обновлённые</option>
              {sort && sort.key !== 'updated' && !['price-asc', 'price-desc'].includes(`${sort.key}-${sort.direction}`)
                ? <option value={`${sort.key}-${sort.direction}`}>{columnLabels[sort.key]} {sort.direction === 'asc' ? '↑' : '↓'}</option> : null}
            </select>
            <ChevronDown aria-hidden="true" />
          </span>
          <span className={`filter-select${selectedTag ? ' filter-select--active' : ''}`}>
            <select value={selectedTag} onChange={(event) => setParam('tag', event.target.value, '')} aria-label="Тег">
              <option value="">Все теги</option>
              {selectedTag && !availableTags.includes(selectedTag) ? <option value={selectedTag}>{selectedTag}</option> : null}
              {availableTags.map((tag) => <option value={tag} key={tag}>{tag}</option>)}
            </select>
            <ChevronDown aria-hidden="true" />
          </span>
          <label className="filters__checkbox"><input type="checkbox" checked={dealsOnly} onChange={(event) => setParam('deals', event.target.checked ? '1' : '', '')} />Выгодные предложения</label>
        </div>
        {hasFilters ? <div className="filters__reset"><Button variant="ghost" icon={<RotateCcw />} onClick={resetFilters}>Сбросить</Button></div> : null}
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
        {cardsQuery.isLoading || groupsQuery.isLoading || dealsOnly && dealsQuery.isLoading ? <LoadingRows /> : cardsQuery.isError || groupsQuery.isError || dealsOnly && dealsQuery.isError ? (
          <div className="state-message"><h2>{dealsOnly && dealsQuery.isError ? 'Не удалось загрузить выгодные предложения' : 'Не удалось загрузить карточки'}</h2><p>Проверьте соединение с API и повторите.</p><Button onClick={() => { void cardsQuery.refetch(); void groupsQuery.refetch(); void dealsQuery.refetch() }}>Повторить</Button></div>
        ) : visibleCards.length === 0 && visibleGroups.length === 0 ? (
          <div className="state-message"><h2>{hasFilters ? 'По выбранным условиям ничего не найдено' : 'Карточек пока нет'}</h2><p>{hasFilters ? 'Попробуйте изменить или сбросить фильтры.' : 'Добавьте первую карточку маркетплейса, чтобы начать собирать историю цены.'}</p><Button variant="primary" onClick={hasFilters ? resetFilters : () => setDrawerOpen(true)}>{hasFilters ? 'Сбросить фильтры' : 'Добавить карточку'}</Button></div>
        ) : view === 'grid' ? (
          <ul className="cards-grid" aria-label="Отслеживаемые карточки маркетплейсов">
            {gridItems.map((item) => item.kind === 'group' ? <li key={`group-${item.group.id}`} className="cards-grid__group">
              <div className="product-group__header">
                <button type="button" className="product-group__toggle" aria-expanded={!collapsedGroups.includes(item.group.id)} onClick={() => toggleGroup(item.group.id)}>{collapsedGroups.includes(item.group.id) ? <ChevronRight /> : <ChevronDown />}<strong>{item.group.name}</strong><small>{item.group.cardIds.length} товаров</small></button><TagList tags={item.group.tags} />
                <span>Цена от {formatPrice(item.group.currentPrice)} · Минимальная {formatPrice(item.group.minimumPrice)}</span>
                <Button variant="ghost" icon={<Pencil />} aria-label={`Изменить группу ${item.group.name}`} onClick={() => setEditingGroup(item.group)}>Изменить</Button>
              </div>
              {!collapsedGroups.includes(item.group.id) ? <ul className="cards-grid cards-grid--nested">{(groupedCards.get(item.group.id) ?? []).map(tile)}</ul> : null}
            </li> : tile(item.card))}
          </ul>
        ) : (
            <table className="cards-table">
              <caption className="sr-only">Отслеживаемые карточки маркетплейсов</caption>
              <thead><tr>{sortableHeader('Карточка', 'title')}{sortableHeader('Маркетплейс', 'marketplace')}{sortableHeader('Цена', 'price')}{sortableHeader('Минимальная', 'minimum')}{sortableHeader('Средняя', 'average')}{sortableHeader('Выгода', 'savings')}{sortableHeader('Наличие', 'availability')}<th><span className="sr-only">Действия</span></th></tr></thead>
              <tbody>
                {orderedItems.map((item) => item.kind === 'group' ? <Fragment key={`group-${item.group.id}`}>
                  <tr className="cards-table__group"><td><button type="button" className="product-group__toggle" aria-expanded={!collapsedGroups.includes(item.group.id)} onClick={() => toggleGroup(item.group.id)}>{collapsedGroups.includes(item.group.id) ? <ChevronRight /> : <ChevronDown />}<strong>{item.group.name}</strong><small>{item.group.cardIds.length} товаров</small></button><TagList tags={item.group.tags} /></td><td>Группа</td><td className="price-cell">{formatPrice(item.group.currentPrice)}</td><td className="price-cell">{formatPrice(item.group.minimumPrice)}</td><td>—</td><td>Сейчас не выгодно</td><td /><td><button type="button" className="product-group__edit" aria-label={`Изменить группу ${item.group.name}`} onClick={() => setEditingGroup(item.group)}><Pencil /></button></td></tr>
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
