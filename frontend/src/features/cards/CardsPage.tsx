import type { ProductGroup } from '../../types/domain'
import { useCatalogModel } from './useCatalogModel'
import { CatalogResults } from './CatalogResults'
import { cn } from '@/lib/utils'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { InputGroup, InputGroupInput, InputGroupAddon } from '@/components/ui/input-group'
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyContent } from '@/components/ui/empty'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { useCallback, useDeferredValue, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { LayoutGrid, List, RotateCcw, Search } from 'lucide-react'
import { useLocation, useSearchParams } from 'react-router-dom'
import { useCatalog } from '../../api/queries'
import { Button } from '../../components/ui/button'
import { LoadingRows } from '../../components/product/LoadingRows'
import { GroupDialog } from './GroupDialog'
import { BulkCardActions } from './BulkCardActions'
import { useCardSelection } from './useCardSelection'
import { hasCatalogFilters } from './catalogModel'
import { useCatalogActions } from '../../components/layout/catalogActions'

export function CardsPage() {
  const { openAdd } = useCatalogActions()
  const location = useLocation()
  const [params, setParams] = useSearchParams()
  // React Router recreates this setter for each search; event callbacks need the latest committed one.
  const paramsSetter = useRef(setParams)
  useLayoutEffect(() => { paramsSetter.current = setParams }, [setParams])
  const [editingGroup, setEditingGroup] = useState<ProductGroup | 'new' | null>(null)
  const [initialGroupCardIds, setInitialGroupCardIds] = useState<number[]>([])
  const [collapsedGroups, setCollapsedGroups] = useState<number[]>([])
  const catalogQuery = useCatalog()
  const selection = useCardSelection(catalogQuery.data?.cards)
  const query = params.get('q') ?? ''
  const deferredSearch = useDeferredValue(location.search)
  const deferredParams = useMemo(() => new URLSearchParams(deferredSearch), [deferredSearch])
  const view = params.get('view') === 'grid' ? 'grid' : 'list'
  const selectedIds = [...selection.selectedIds]
  const hasFilters = hasCatalogFilters(params)
  const { deals, orderedItems, groupedCards, matchingCount, totalCount } = useCatalogModel(catalogQuery.data, deferredParams)
  const returnTo = location.pathname + deferredSearch

  function openCreateGroup(ids: number[]) {
    setInitialGroupCardIds(ids)
    setEditingGroup('new')
  }

  const setParam = useCallback((name: string, value: string, defaultValue = 'all') => {
    paramsSetter.current((current) => {
      const next = new URLSearchParams(current)
      if (!value || value === defaultValue) next.delete(name)
      else next.set(name, value)
      return next
    }, { replace: true, flushSync: true })
  }, [])

  const toggleGroup = useCallback((groupId: number) => {
    setCollapsedGroups((current) => current.includes(groupId) ? current.filter((id) => id !== groupId) : [...current, groupId])
  }, [])

  const sortResults = useCallback((value: string) => setParam('sort', value), [setParam])
  const editGroup = useCallback((group: ProductGroup) => {
    setEditingGroup(catalogQuery.data?.groups.find(original => original.id === group.id) ?? group)
  }, [catalogQuery.data?.groups])

  function resetFilters() {
    // Commit the reset before another control can reuse the previous search params.
    const next = new URLSearchParams(view === 'grid' ? { view: 'grid' } : {})
    setParams(next, { replace: true, flushSync: true })
  }

  return (
    <section className="page cards-page" aria-busy={location.search !== deferredSearch}>
      {catalogQuery.isError && catalogQuery.data ? <Alert variant="destructive"><AlertDescription>Не удалось обновить каталог. <Button variant="link" type="button" onClick={() => void catalogQuery.refetch()}>Повторить</Button></AlertDescription></Alert> : null}

      <div className="mb-5 flex items-center gap-4">
        <h1>Карточки товаров</h1>
        <span className="whitespace-nowrap text-sm text-muted-foreground">Показано {matchingCount} из {totalCount} товаров</span>
      </div>
      <InputGroup className="catalog-search">
          <InputGroupAddon><Search aria-hidden="true" /></InputGroupAddon>
          <InputGroupInput value={query} onChange={(event) => setParam('q', event.target.value, '')} placeholder="Название или артикул" aria-label="Поиск по названию или артикулу" />
      </InputGroup>
      <div className="cards-view-bar justify-start">
        <div className="flex items-center gap-2">
          <ToggleGroup type="single" value={view} onValueChange={(value) => { if (value) setParam('view', value, 'list') }} variant="outline" spacing={0} aria-label="Вид карточек">
            <ToggleGroupItem value="list" aria-label="Список" title="Список"><List aria-hidden="true" /></ToggleGroupItem>
            <ToggleGroupItem value="grid" aria-label="Сетка" title="Сетка"><LayoutGrid aria-hidden="true" /></ToggleGroupItem>
          </ToggleGroup>
          {hasFilters ? <Button variant="ghost" size="sm" onClick={resetFilters}><RotateCcw data-icon="inline-start" />Сбросить</Button> : null}
        </div>
      </div>

      <BulkCardActions selectedIds={selectedIds} cards={catalogQuery.data?.cards ?? []} groups={catalogQuery.data?.groups ?? []}
        onCreateGroup={() => openCreateGroup(selectedIds)} onProcessed={selection.clearProcessed} onClear={selection.clear} />

      <div className={cn(view === 'list' || catalogQuery.isLoading || catalogQuery.isError || (orderedItems.length === 0) ? 'table-surface' : '')}>
        {catalogQuery.isLoading ? <LoadingRows /> : (catalogQuery.isError && !catalogQuery.data) ? (
          <Empty><EmptyHeader><EmptyTitle>Не удалось загрузить каталог</EmptyTitle><EmptyDescription>Проверьте соединение с API и повторите.</EmptyDescription></EmptyHeader><EmptyContent><Button onClick={() => { void catalogQuery.refetch() }}>Повторить</Button></EmptyContent></Empty>
        ) : orderedItems.length === 0 ? (
          <Empty><EmptyHeader><EmptyTitle>{hasFilters ? 'По выбранным условиям ничего не найдено' : 'Карточек пока нет'}</EmptyTitle><EmptyDescription>{hasFilters ? 'Попробуйте изменить или сбросить фильтры.' : 'Добавьте первую карточку маркетплейса, чтобы начать собирать историю цены.'}</EmptyDescription></EmptyHeader><EmptyContent><Button variant="default" onClick={hasFilters ? resetFilters : openAdd}>{hasFilters ? 'Сбросить фильтры' : 'Добавить карточку'}</Button></EmptyContent></Empty>
        ) : <CatalogResults sort={deferredParams.get('sort')} onSort={sortResults} view={view} items={orderedItems} groupedCards={groupedCards} deals={deals}
          selectedIds={selection.selectedIds} onSelect={selection.toggle} collapsedGroups={collapsedGroups}
          onToggleGroup={toggleGroup} onEditGroup={editGroup} returnTo={returnTo} />
        }
      </div>
      {editingGroup ? <GroupDialog key={editingGroup === 'new' ? 'new' : editingGroup.id} group={editingGroup === 'new' ? null : editingGroup}
        cards={catalogQuery.data?.cards ?? []} initialCardIds={editingGroup === 'new' ? initialGroupCardIds : []}
        onSaved={editingGroup === 'new' ? selection.clearProcessed : undefined} onClose={() => setEditingGroup(null)} /> : null}
    </section>
  )
}
