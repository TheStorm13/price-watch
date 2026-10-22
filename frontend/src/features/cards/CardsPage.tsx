import { cn } from '@/lib/utils'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Checkbox } from '@/components/ui/checkbox'
import { InputGroup, InputGroupInput, InputGroupAddon } from '@/components/ui/input-group'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyContent } from '@/components/ui/empty'
import { Badge } from '@/components/ui/badge'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableCaption } from '@/components/ui/table'
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Fragment, useCallback, useDeferredValue, useMemo, useState } from 'react'
import { ArrowDown, ArrowUp, ChevronDown, ChevronRight, FolderPlus, LayoutGrid, List, Pencil, Plus, RefreshCw, RotateCcw, Search } from 'lucide-react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useCatalog, useDeleteCard, useUpdateCard } from '../../api/queries'
import { Button } from '../../components/ui/button'
import { CardActionsMenu } from '../../components/product/CardActionsMenu'
import { AvailabilityStatus } from '../../components/product/AvailabilityStatus'
import { LoadingRows } from '../../components/product/LoadingRows'
import { MarketplaceMark } from '../../components/product/MarketplaceMark'
import { ProductImage } from '../../components/product/ProductImage'
import { TagList } from '../../components/product/TagList'
import { useCollection } from '../collection/CollectionProvider'
import type { MarketplaceCard, ProductGroup } from '../../types/domain'
import { formatDateTime, formatPrice, formatRelativeTime } from '../../utils/format'
import { AddCardDrawer } from './AddCardDrawer'
import { cardItem, catalogItems, columnSortKeys, compareItems, matchesItem, parseSort, type ColumnSortKey } from './catalogItems'
import { ImportExportControls } from './ImportExportControls'
import { GroupDialog } from './GroupDialog'
import { BulkCardActions } from './BulkCardActions'
import { useCardSelection } from './useCardSelection'

const collator = new Intl.Collator('ru', { numeric: true, sensitivity: 'base' })
const columnLabels: Record<ColumnSortKey, string> = {
  title: 'Карточка', marketplace: 'Маркетплейс', price: 'Цена', minimum: 'Минимальная',
  average: 'Средняя', savings: 'Выгода', availability: 'Наличие',
}

export function CardsPage() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editingGroup, setEditingGroup] = useState<ProductGroup | 'new' | null>(null)
  const [initialGroupCardIds, setInitialGroupCardIds] = useState<number[]>([])
  const [collapsedGroups, setCollapsedGroups] = useState<number[]>([])
  const [transferStatus, setTransferStatus] = useState<{ message: string; kind: 'success' | 'error' } | null>(null)
  const catalogQuery = useCatalog()
  const selection = useCardSelection(catalogQuery.data?.cards)
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
  const selectedIds = [...selection.selectedIds]
  const hasFilters = Boolean(query || marketplace !== 'all' || status !== 'all' || sort || dealsOnly || selectedTag)
  const deals = useMemo(() => new Map((catalogQuery.data?.deals ?? []).map((deal) => [deal.card.id, deal])), [catalogQuery.data?.deals])
  const allItems = useMemo(() => catalogItems(catalogQuery.data?.cards ?? [], catalogQuery.data?.groups ?? [], deals),
    [catalogQuery.data?.cards, catalogQuery.data?.groups, deals])
  const availableTags = useMemo(() => [...new Set(allItems.flatMap((item) => item.card?.tags ?? []))].sort(collator.compare), [allItems])

  function openCreateGroup(ids: number[]) {
    setInitialGroupCardIds(ids)
    setEditingGroup('new')
  }

  const setParam = useCallback((name: string, value: string, defaultValue = 'all') => {
    setParams((current) => {
      const next = new URLSearchParams(current)
      if (!value || value === defaultValue) next.delete(name)
      else next.set(name, value)
      return next
    }, { replace: true, flushSync: true })
  }, [setParams])

  const orderedItems = useMemo(() => allItems.filter((item) => matchesItem(item, {
    query: deferredQuery, marketplace, status, tag: selectedTag, dealsOnly,
  })).toSorted((left, right) => compareItems(left, right, sort)),
  [allItems, deferredQuery, marketplace, status, selectedTag, dealsOnly, sort])

  const groupedCards = useMemo(() => {
    const byGroup = new Map<number, MarketplaceCard[]>()
    for (const card of catalogQuery.data?.cards ?? []) {
      if (card.groupId == null) continue
      const members = byGroup.get(card.groupId) ?? []
      members.push(card)
      byGroup.set(card.groupId, members)
    }
    for (const members of byGroup.values()) members.sort((left, right) =>
      compareItems(cardItem(left, deals), cardItem(right, deals), sort))
    return byGroup
  }, [catalogQuery.data?.cards, deals, sort])

  function toggleSort(key: ColumnSortKey) {
    const next = sort?.key === key ? (sort.direction === 'asc' ? `${key}-desc` : '') : `${key}-asc`
    setParam('sort', next, '')
  }

  function sortableHeader(label: string, key: ColumnSortKey) {
    const direction = sort?.key === key ? sort.direction : null
    return <TableHead scope="col" aria-sort={direction === 'asc' ? 'ascending' : direction === 'desc' ? 'descending' : 'none'}>
      <Button variant="ghost" type="button" className={cn('cards-table__sort h-11.5 px-0', direction && 'is-active')} onClick={() => toggleSort(key)}
        title={direction === 'asc' ? 'Сортировать по убыванию' : direction === 'desc' ? 'Сбросить сортировку' : 'Сортировать по возрастанию'}>
        {label}<span className="cards-table__sort-icon" aria-hidden="true">{direction === 'desc' ? <ArrowDown /> : <ArrowUp />}</span>
      </Button>
    </TableHead>
  }

  function toggleGroup(groupId: number) {
    setCollapsedGroups((current) => current.includes(groupId) ? current.filter((id) => id !== groupId) : [...current, groupId])
  }

  function resetFilters() {
    // Commit the reset before another control can reuse the previous search params.
    setParams(view === 'grid' ? { view: 'grid' } : {}, { replace: true, flushSync: true })
  }

  function actions(card: MarketplaceCard) {
    return <CardActionsMenu cardTitle={card.title ?? card.externalId} dealsEnabled={card.dealsEnabled}
      onRefresh={card.marketplace === 'ozon' ? () => collection.start(card.id) : undefined} refreshDisabled={collection.isStarting}
      onToggle={() => updateCard.mutateAsync({ cardId: card.id, input: { dealsEnabled: !card.dealsEnabled } })}
      onDelete={() => deleteCard.mutateAsync(card.id)} />
  }

  function dealStatus(card: MarketplaceCard) {
    return <>
      {!card.dealsEnabled ? <Badge variant="warning" className="tracking-status" title="Не участвует в выгодных">Не участвует в выгодных</Badge> : null}
    </>
  }

  function saving(card: MarketplaceCard) {
    const deal = deals.get(card.id)
    return deal ? <span className="deal-savings">{formatPrice(deal.savings)}</span> : 'Сейчас не выгодно'
  }

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

  function tile(card: MarketplaceCard) {
    return <Card key={card.id} asChild className="grid gap-0 py-0"><li className="cards-grid__item">
      <div className="cards-grid__actions">{actions(card)}</div>
      <CardHeader className="contents"><Link className="cards-grid__link" to={`/cards/${card.id}`}>
        <span className="cards-grid__media"><ProductImage card={card} large /></span>
        <CardTitle className="contents"><span className="cards-grid__title" title={card.title ?? 'Без названия'}>{card.title ?? 'Без названия'}</span></CardTitle>
        <CardDescription className="contents"><span className="cards-grid__id">ID: {card.externalId}</span></CardDescription>
      </Link></CardHeader>
      <CardContent className="contents"><div className="cards-grid__tags" title={card.tags?.join(', ')}><TagList tags={card.tags} /></div>
      <div className="cards-grid__details"><MarketplaceMark marketplace={card.marketplace} /></div>
      <dl className="cards-grid__prices"><div><dt>Цена</dt><dd>{formatPrice(card.currentPrice)}</dd></div><div><dt>Минимальная</dt><dd>{formatPrice(card.minimumPrice)}</dd></div><div><dt>Средняя</dt><dd>{formatPrice(card.averagePrice)}</dd></div><div><dt>Выгода</dt><dd>{saving(card)}</dd></div></dl>
      </CardContent><CardFooter className="contents"><div className="cards-grid__details"><time dateTime={card.lastObservedAt ? card.updatedAt : undefined} title={formatDateTime(card.lastObservedAt ? card.updatedAt : null)}>{formatRelativeTime(card.lastObservedAt ? card.updatedAt : null)}</time><AvailabilityStatus value={card.currentAvailability} /></div>
      <div className="cards-grid__tracking">{dealStatus(card)}</div>
    </CardFooter></li></Card>
  }

  function row(card: MarketplaceCard, nested = false) {
    return <TableRow key={card.id} className={cn('cards-table__product', nested && 'cards-table__nested', selection.selectedIds.has(card.id) && 'is-selected')} onClick={() => navigate(`/cards/${card.id}`)}>
      <TableCell className="cards-table__selection py-2"><Checkbox aria-label={`Выбрать карточку ${card.title ?? card.externalId}`}
        checked={selection.selectedIds.has(card.id)} onClick={(event) => event.stopPropagation()} onCheckedChange={() => selection.toggle(card.id)} /></TableCell>
      <TableCell className="py-2"><div className="card-identity"><ProductImage card={card} /><span><strong title={card.title ?? 'Без названия'}>{card.title ?? 'Без названия'}</strong><small>ID: {card.externalId}</small><TagList tags={card.tags} />{dealStatus(card)}</span></div></TableCell>
      <TableCell className="py-2"><MarketplaceMark marketplace={card.marketplace} /></TableCell>
      <TableCell className="price-cell py-2">{formatPrice(card.currentPrice)}</TableCell>
      <TableCell className="price-cell py-2">{formatPrice(card.minimumPrice)}</TableCell>
      <TableCell className="price-cell py-2">{formatPrice(card.averagePrice)}</TableCell>
      <TableCell className="py-2">{saving(card)}</TableCell>
      <TableCell className="py-2"><AvailabilityStatus value={card.currentAvailability} /></TableCell>
      <TableCell className="py-2">{actions(card)}</TableCell>
    </TableRow>
  }

  return (
    <section className="page cards-page">
      <header className="page-header">
        <div><h1>Карточки</h1><p>Текущие цены и история отслеживаемых карточек</p></div>
        <div className="page-actions">
          <ImportExportControls onStatus={(message, kind) => setTransferStatus({ message, kind })} />
          <Button variant="outline" onClick={() => openCreateGroup([])}><FolderPlus data-icon="inline-start" />Создать группу</Button>
          <Button variant="outline" onClick={() => collection.start()} disabled={collection.isStarting}><RefreshCw data-icon="inline-start" />Обновить цены</Button>
          <Button variant="default" onClick={() => setDrawerOpen(true)}><Plus data-icon="inline-start" />Добавить карточку</Button>
        </div>
      </header>
      {transferStatus ? <Alert variant={transferStatus.kind === 'error' ? 'destructive' : 'default'}
        role={transferStatus.kind === 'error' ? 'alert' : 'status'}><AlertDescription>{transferStatus.message}</AlertDescription></Alert> : null}
      {collection.startError ? <Alert variant="destructive"><AlertDescription>{collection.startError}</AlertDescription></Alert> : null}
      {catalogQuery.isError && catalogQuery.data ? <Alert variant="destructive"><AlertDescription>Не удалось обновить каталог. <Button variant="link" type="button" onClick={() => void catalogQuery.refetch()}>Повторить</Button></AlertDescription></Alert> : null}

      <div className="filters">
        <InputGroup className="max-w-[280px] flex-[1_1_230px]">
          <InputGroupAddon><Search aria-hidden="true" /></InputGroupAddon>
          <InputGroupInput value={query} onChange={(event) => setParam('q', event.target.value, '')} placeholder="Название или ID" aria-label="Поиск карточек" />
        </InputGroup>
        <div className="filters__selects">
          <span className={cn('filter-select', marketplace !== 'all' && 'filter-select--active')}>
            <Select value={marketplace} onValueChange={(value) => setParam('marketplace', value)}>
              <SelectTrigger className="w-full" aria-label="Маркетплейс"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">Все маркетплейсы</SelectItem>
                  <SelectItem value="ozon">Ozon</SelectItem>
                  <SelectItem value="wildberries">Wildberries</SelectItem>
                  <SelectItem value="aliexpress">AliExpress</SelectItem>
                  <SelectItem value="yandex-market">Яндекс Маркет</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>

          </span>
          <span className={cn('filter-select filter-select--status', status !== 'all' && 'filter-select--active')}>
            <Select value={status} onValueChange={(value) => setParam('status', value)}>
              <SelectTrigger className="w-full" aria-label="Состояние"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">Все состояния</SelectItem>
                  <SelectItem value="in_stock">В наличии</SelectItem>
                  <SelectItem value="out_of_stock">Нет в наличии</SelectItem>
                  <SelectItem value="no_data">Нет данных</SelectItem>
                  <SelectItem value="deals_disabled">Не участвует в выгодных</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>

          </span>
          <span className={cn('filter-select filter-select--sort', sort && 'filter-select--active')}>
            <Select value={sort ? `${sort.key}-${sort.direction}` : 'default'} onValueChange={(value) => setParam('sort', value, 'default')}>
              <SelectTrigger className="w-full" aria-label="Сортировка"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="default">По умолчанию</SelectItem>
                  <SelectItem value="price-asc">Сначала дешевле</SelectItem>
                  <SelectItem value="price-desc">Сначала дороже</SelectItem>
                  <SelectItem value="updated-desc">Недавно обновлённые</SelectItem>
                  {sort && sort.key !== 'updated' && !['price-asc', 'price-desc'].includes(`${sort.key}-${sort.direction}`)
                    ? <SelectItem value={`${sort.key}-${sort.direction}`}>{columnLabels[sort.key]} {sort.direction === 'asc' ? '↑' : '↓'}</SelectItem> : null}
                </SelectGroup>
              </SelectContent>
            </Select>

          </span>
          <span className={cn('filter-select', selectedTag && 'filter-select--active')}>
            <Select value={selectedTag ? `tag:${selectedTag}` : 'all'} onValueChange={(value) => setParam('tag', value === 'all' ? '' : value.slice(4), '')}>
              <SelectTrigger className="w-full" aria-label="Тег"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">Все теги</SelectItem>
                  {selectedTag && !availableTags.includes(selectedTag) ? <SelectItem value={`tag:${selectedTag}`}>{selectedTag}</SelectItem> : null}
                  {availableTags.map((tag) => <SelectItem value={`tag:${tag}`} key={tag}>{tag}</SelectItem>)}
                </SelectGroup>
              </SelectContent>
            </Select>

          </span>
          <div className="flex items-center gap-2"><Checkbox id="deals-only" checked={dealsOnly} onCheckedChange={(checked) => setParam('deals', checked === true ? '1' : '', '')} /><label htmlFor="deals-only" className="filters__checkbox">Выгодные предложения</label></div>
        </div>
        {hasFilters ? <div className="filters__reset"><Button variant="ghost" onClick={resetFilters}><RotateCcw data-icon="inline-start" />Сбросить</Button></div> : null}
      </div>

      <div className="cards-view-bar">
        <span>{orderedItems.length} из {allItems.length}</span>
        <ToggleGroup type="single" value={view} onValueChange={(value) => { if (value) setParam('view', value, 'list') }} variant="outline" spacing={0} aria-label="Вид карточек">
          <ToggleGroupItem value="list" aria-label="Список" title="Список"><List aria-hidden="true" /></ToggleGroupItem>
          <ToggleGroupItem value="grid" aria-label="Сетка" title="Сетка"><LayoutGrid aria-hidden="true" /></ToggleGroupItem>
        </ToggleGroup>
      </div>

      <BulkCardActions selectedIds={selectedIds} cards={catalogQuery.data?.cards ?? []} groups={catalogQuery.data?.groups ?? []}
        onCreateGroup={() => openCreateGroup(selectedIds)} onProcessed={selection.clearProcessed} onClear={selection.clear} />

      <div className={cn(view === 'list' || catalogQuery.isLoading || catalogQuery.isError || (orderedItems.length === 0) ? 'table-surface' : '')}>
        {catalogQuery.isLoading ? <LoadingRows /> : (catalogQuery.isError && !catalogQuery.data) ? (
          <Empty><EmptyHeader><EmptyTitle>Не удалось загрузить каталог</EmptyTitle><EmptyDescription>Проверьте соединение с API и повторите.</EmptyDescription></EmptyHeader><EmptyContent><Button onClick={() => { void catalogQuery.refetch() }}>Повторить</Button></EmptyContent></Empty>
        ) : orderedItems.length === 0 ? (
          <Empty><EmptyHeader><EmptyTitle>{hasFilters ? 'По выбранным условиям ничего не найдено' : 'Карточек пока нет'}</EmptyTitle><EmptyDescription>{hasFilters ? 'Попробуйте изменить или сбросить фильтры.' : 'Добавьте первую карточку маркетплейса, чтобы начать собирать историю цены.'}</EmptyDescription></EmptyHeader><EmptyContent><Button variant="default" onClick={hasFilters ? resetFilters : () => setDrawerOpen(true)}>{hasFilters ? 'Сбросить фильтры' : 'Добавить карточку'}</Button></EmptyContent></Empty>
        ) : view === 'grid' ? (
          <ul className="cards-grid" aria-label="Отслеживаемые карточки маркетплейсов">
            {orderedItems.map((item) => item.kind === 'group' ? <li key={`group-${item.group.id}`} className="cards-grid__group">
              <div className="product-group__header">
                <Button variant="ghost" type="button" className="product-group__toggle px-0" aria-expanded={!collapsedGroups.includes(item.group.id)} onClick={() => toggleGroup(item.group.id)}>{collapsedGroups.includes(item.group.id) ? <ChevronRight /> : <ChevronDown />}<strong>{item.group.name}</strong><small>{item.group.cardIds.length} товаров</small></Button><TagList tags={item.card?.tags} />
                <div className="flex flex-wrap items-center gap-3">
                  {item.card ? <><ProductImage card={item.card} /><MarketplaceMark marketplace={item.card.marketplace} /></> : null}
                  <span>Цена {formatPrice(item.card?.currentPrice)} · Минимальная {formatPrice(item.card?.minimumPrice)} · Средняя {formatPrice(item.card?.averagePrice)}</span>
                  {groupSaving(item.group)}<AvailabilityStatus value={item.card?.currentAvailability ?? null} />
                  {groupDetails(item.group)}
                </div>
                <Button variant="ghost" aria-label={`Изменить группу ${item.group.name}`} onClick={() => setEditingGroup(item.group)}><Pencil data-icon="inline-start" />Изменить</Button>
              </div>
              {!collapsedGroups.includes(item.group.id) ? <ul className="cards-grid cards-grid--nested">{(groupedCards.get(item.group.id) ?? []).map(tile)}</ul> : null}
            </li> : tile(item.card))}
          </ul>
        ) : (
            <Table className="cards-table">
              <TableCaption className="sr-only">Отслеживаемые карточки маркетплейсов</TableCaption>
              <TableHeader><TableRow><TableHead className="cards-table__selection py-0"><span className="sr-only">Выбор</span></TableHead>{sortableHeader('Карточка', 'title')}{sortableHeader('Маркетплейс', 'marketplace')}{sortableHeader('Цена', 'price')}{sortableHeader('Минимальная', 'minimum')}{sortableHeader('Средняя', 'average')}{sortableHeader('Выгода', 'savings')}{sortableHeader('Наличие', 'availability')}<TableHead><span className="sr-only">Действия</span></TableHead></TableRow></TableHeader>
              <TableBody>
                {orderedItems.map((item) => item.kind === 'group' ? <Fragment key={`group-${item.group.id}`}>
                  <tr className="cards-table__group-gap" aria-hidden="true"><td colSpan={9} /></tr>
                  <TableRow className="cards-table__group"><TableCell className="cards-table__selection py-0" /><TableCell className="py-0"><Button variant="ghost" type="button" className="product-group__toggle px-0" aria-expanded={!collapsedGroups.includes(item.group.id)} onClick={() => toggleGroup(item.group.id)}>{collapsedGroups.includes(item.group.id) ? <ChevronRight /> : <ChevronDown />}<strong>{item.group.name}</strong><small>{item.group.cardIds.length} товаров</small></Button><TagList tags={item.card?.tags} />{groupDetails(item.group)}</TableCell><TableCell className="py-0">{item.card ? <MarketplaceMark marketplace={item.card.marketplace} /> : '—'}</TableCell><TableCell className="price-cell py-0">{formatPrice(item.group.currentPrice)}</TableCell><TableCell className="price-cell py-0">{formatPrice(item.group.minimumPrice)}</TableCell><TableCell className="price-cell py-0">{formatPrice(item.card?.averagePrice)}</TableCell><TableCell className="py-0">{groupSaving(item.group)}</TableCell><TableCell className="py-0"><AvailabilityStatus value={item.card?.currentAvailability ?? null} /></TableCell><TableCell className="py-0"><Button variant="ghost" size="icon-sm" type="button" aria-label={`Изменить группу ${item.group.name}`} onClick={() => setEditingGroup(item.group)}><Pencil /></Button></TableCell></TableRow>
                  {!collapsedGroups.includes(item.group.id) ? (groupedCards.get(item.group.id) ?? []).map((card) => row(card, true)) : null}
                  <tr className="cards-table__group-gap" aria-hidden="true"><td colSpan={9} /></tr>
                </Fragment> : row(item.card))}
              </TableBody>
            </Table>
        )}
      </div>
      <AddCardDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
      {editingGroup ? <GroupDialog key={editingGroup === 'new' ? 'new' : editingGroup.id} group={editingGroup === 'new' ? null : editingGroup}
        cards={catalogQuery.data?.cards ?? []} initialCardIds={editingGroup === 'new' ? initialGroupCardIds : []}
        onSaved={editingGroup === 'new' ? selection.clearProcessed : undefined} onClose={() => setEditingGroup(null)} /> : null}
    </section>
  )
}
