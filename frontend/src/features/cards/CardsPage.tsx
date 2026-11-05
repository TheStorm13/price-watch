import type { ProductGroup } from '../../types/domain'
import { useCatalogModel } from './useCatalogModel'
import { CatalogResults } from './CatalogResults'
import { cn } from '@/lib/utils'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { InputGroup, InputGroupInput, InputGroupAddon } from '@/components/ui/input-group'
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyContent } from '@/components/ui/empty'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useCallback, useDeferredValue, useMemo, useState } from 'react'
import { FolderPlus, LayoutGrid, List, Plus, RefreshCw, RotateCcw, Search } from 'lucide-react'
import { useLocation, useSearchParams } from 'react-router-dom'
import { useCatalog } from '../../api/queries'
import { Button } from '../../components/ui/button'
import { LoadingRows } from '../../components/product/LoadingRows'
import { useCollectionCommands } from '../collection/CollectionProvider'
import { AddCardDrawer } from './AddCardDrawer'
import { columnLabels, parseSort, type ColumnSortKey } from './catalogItems'
import { ImportExportControls } from './ImportExportControls'
import { GroupDialog } from './GroupDialog'
import { BulkCardActions } from './BulkCardActions'
import { useCardSelection } from './useCardSelection'
import { SidebarDemoSlot, useSidebarDemo } from '../sidebar-demo/SidebarDemoSlot'

export function CardsPage() {
  const sidebarDemo = useSidebarDemo()
  const location = useLocation()
  const [params, setParams] = useSearchParams()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editingGroup, setEditingGroup] = useState<ProductGroup | 'new' | null>(null)
  const [initialGroupCardIds, setInitialGroupCardIds] = useState<number[]>([])
  const [collapsedGroups, setCollapsedGroups] = useState<number[]>([])
  const [transferStatus, setTransferStatus] = useState<{ message: string; kind: 'success' | 'error' } | null>(null)
  const catalogQuery = useCatalog()
  const selection = useCardSelection(catalogQuery.data?.cards)
  const collection = useCollectionCommands()
  const query = params.get('q') ?? ''
  const deferredQuery = useDeferredValue(query.trim().toLowerCase())
  const marketplace = params.get('marketplace') ?? 'all'
  const status = params.get('status') ?? 'all'
  const sortParam = params.get('sort')
  const sort = useMemo(() => parseSort(sortParam), [sortParam])
  const view = params.get('view') === 'grid' ? 'grid' : 'list'
  const dealParam = params.get('deals')
  const dealFilter = dealParam === 'deals' || dealParam === 'non_deals' ? dealParam : 'all'
  const selectedTag = params.get('tag') ?? ''
  const selectedIds = [...selection.selectedIds]
  const hasFilters = Boolean(query || marketplace !== 'all' || status !== 'all' || sort || dealFilter !== 'all' || selectedTag)
  const { deals, allItems, availableTags, orderedItems, groupedCards } = useCatalogModel(catalogQuery.data,
    deferredQuery, marketplace, status, selectedTag, dealFilter, sort)
  const returnTo = useDeferredValue(location.pathname + location.search)

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


  const toggleSort = useCallback((key: ColumnSortKey) => {
    const next = sort?.key === key ? (sort.direction === 'asc' ? `${key}-desc` : '') : `${key}-asc`
    setParam('sort', next, '')
  }, [sort, setParam])


  const toggleGroup = useCallback((groupId: number) => {
    setCollapsedGroups((current) => current.includes(groupId) ? current.filter((id) => id !== groupId) : [...current, groupId])
  }, [])

  function resetFilters() {
    // Commit the reset before another control can reuse the previous search params.
    const next = new URLSearchParams(view === 'grid' ? { view: 'grid' } : {})
    if (sidebarDemo && params.has('sidebar')) next.set('sidebar', params.get('sidebar')!)
    setParams(next, { replace: true, flushSync: true })
  }


  return (
    <section className="page cards-page">
      <header className="page-header">
        <div><h1>Карточки</h1><p>Текущие цены и история отслеживаемых карточек</p></div>
        <div className="page-actions">
          {!sidebarDemo ? <ImportExportControls onStatus={(message, kind) => setTransferStatus({ message, kind })} /> : null}
          <SidebarDemoSlot name="group"><Button className={sidebarDemo ? 'justify-start' : undefined} variant="outline" onClick={() => openCreateGroup([])}><FolderPlus data-icon="inline-start" />Создать группу</Button></SidebarDemoSlot>
          {!sidebarDemo ? <>
          <Button variant="outline" onClick={() => collection.start()} disabled={collection.isStarting}><RefreshCw data-icon="inline-start" />Обновить цены</Button>
          <Button variant="default" onClick={() => setDrawerOpen(true)}><Plus data-icon="inline-start" />Добавить карточку</Button>
          </> : null}
        </div>
      </header>
      {transferStatus ? <Alert variant={transferStatus.kind === 'error' ? 'destructive' : 'default'}
        role={transferStatus.kind === 'error' ? 'alert' : 'status'}><AlertDescription>{transferStatus.message}</AlertDescription></Alert> : null}
      {collection.startError ? <Alert variant="destructive"><AlertDescription>{collection.startError}</AlertDescription></Alert> : null}
      {catalogQuery.isError && catalogQuery.data ? <Alert variant="destructive"><AlertDescription>Не удалось обновить каталог. <Button variant="link" type="button" onClick={() => void catalogQuery.refetch()}>Повторить</Button></AlertDescription></Alert> : null}

      <SidebarDemoSlot name="filters"><div className="filters">
        <InputGroup className="filters__search">
          <InputGroupAddon><Search aria-hidden="true" /></InputGroupAddon>
          <InputGroupInput value={query} onChange={(event) => setParam('q', event.target.value, '')} placeholder="Название или ID" aria-label="Поиск карточек" />
        </InputGroup>
        <div className="filters__selects">
          <span data-label="Маркетплейс" className={cn('filter-select', marketplace !== 'all' && 'filter-select--active')}>
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
          <span data-label="Состояние" className={cn('filter-select filter-select--status', status !== 'all' && 'filter-select--active')}>
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
          <span data-label="Сортировка" className={cn('filter-select filter-select--sort', sort && 'filter-select--active')}>
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
          <span data-label="Тег" className={cn('filter-select', selectedTag && 'filter-select--active')}>
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
          <span data-label="Выгодность" className={cn('filter-select', dealFilter !== 'all' && 'filter-select--active')}>
            <Select value={dealFilter} onValueChange={(value) => setParam('deals', value)}>
              <SelectTrigger className="w-full" aria-label="Выгодность"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">Все</SelectItem>
                  <SelectItem value="deals">Выгодные</SelectItem>
                  <SelectItem value="non_deals">Не выгодные</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </span>
        </div>
      </div>

      </SidebarDemoSlot>

      <div className="cards-view-bar">
        <span>{orderedItems.length} из {allItems.length}</span>
        <div className="flex items-center gap-2">
          {hasFilters ? <Button variant="ghost" size="sm" onClick={resetFilters}><RotateCcw data-icon="inline-start" />Сбросить</Button> : null}
          <ToggleGroup type="single" value={view} onValueChange={(value) => { if (value) setParam('view', value, 'list') }} variant="outline" spacing={0} aria-label="Вид карточек">
            <ToggleGroupItem value="list" aria-label="Список" title="Список"><List aria-hidden="true" /></ToggleGroupItem>
            <ToggleGroupItem value="grid" aria-label="Сетка" title="Сетка"><LayoutGrid aria-hidden="true" /></ToggleGroupItem>
          </ToggleGroup>
        </div>
      </div>

      <BulkCardActions selectedIds={selectedIds} cards={catalogQuery.data?.cards ?? []} groups={catalogQuery.data?.groups ?? []}
        onCreateGroup={() => openCreateGroup(selectedIds)} onProcessed={selection.clearProcessed} onClear={selection.clear} />

      <div className={cn(view === 'list' || catalogQuery.isLoading || catalogQuery.isError || (orderedItems.length === 0) ? 'table-surface' : '')}>
        {catalogQuery.isLoading ? <LoadingRows /> : (catalogQuery.isError && !catalogQuery.data) ? (
          <Empty><EmptyHeader><EmptyTitle>Не удалось загрузить каталог</EmptyTitle><EmptyDescription>Проверьте соединение с API и повторите.</EmptyDescription></EmptyHeader><EmptyContent><Button onClick={() => { void catalogQuery.refetch() }}>Повторить</Button></EmptyContent></Empty>
        ) : orderedItems.length === 0 ? (
          <Empty><EmptyHeader><EmptyTitle>{hasFilters ? 'По выбранным условиям ничего не найдено' : 'Карточек пока нет'}</EmptyTitle><EmptyDescription>{hasFilters ? 'Попробуйте изменить или сбросить фильтры.' : 'Добавьте первую карточку маркетплейса, чтобы начать собирать историю цены.'}</EmptyDescription></EmptyHeader><EmptyContent><Button variant="default" onClick={hasFilters ? resetFilters : () => setDrawerOpen(true)}>{hasFilters ? 'Сбросить фильтры' : 'Добавить карточку'}</Button></EmptyContent></Empty>
        ) : <CatalogResults view={view} items={orderedItems} groupedCards={groupedCards} deals={deals}
          selectedIds={selection.selectedIds} onSelect={selection.toggle} collapsedGroups={collapsedGroups}
          onToggleGroup={toggleGroup} onEditGroup={setEditingGroup} sort={sort} onSort={toggleSort} returnTo={returnTo} />
        }
      </div>
      <AddCardDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
      {editingGroup ? <GroupDialog key={editingGroup === 'new' ? 'new' : editingGroup.id} group={editingGroup === 'new' ? null : editingGroup}
        cards={catalogQuery.data?.cards ?? []} initialCardIds={editingGroup === 'new' ? initialGroupCardIds : []}
        onSaved={editingGroup === 'new' ? selection.clearProcessed : undefined} onClose={() => setEditingGroup(null)} /> : null}
    </section>
  )
}
