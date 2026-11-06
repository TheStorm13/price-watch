import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { useMemo, useState } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { BarChart3, FolderPlus, Globe2, Plus, RefreshCw } from 'lucide-react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { apiModeLabel, isDesktopMode } from '../../api/client'
import { useCatalog } from '../../api/queries'
import { ActiveCollectionPanel } from '../../features/collection/ActiveCollectionPanel'
import { useCollection } from '../../features/collection/CollectionProvider'
import { BackgroundSettings } from '../../features/background/BackgroundSettings'
import { useDesktopRuntime } from '../../app/desktopRuntime'
import { AddCardDrawer } from '../../features/cards/AddCardDrawer'
import { GroupDialog } from '../../features/cards/GroupDialog'
import { ImportExportControls } from '../../features/cards/ImportExportControls'
import { CatalogFilters } from '../../features/cards/CatalogFilters'
import { CatalogActionsContext } from './catalogActions'

export function AppShell() {
  const location = useLocation()
  const navigate = useNavigate()
  const catalog = useCatalog()
  const { run, isStarting, start, startError } = useCollection()
  const { serviceError, retryServices } = useDesktopRuntime()
  const [browserError, setBrowserError] = useState<string | null>(null)
  const [openingBrowser, setOpeningBrowser] = useState(false)
  const [adding, setAdding] = useState(false)
  const [creatingGroup, setCreatingGroup] = useState(false)
  const [transferStatus, setTransferStatus] = useState<{ message: string; kind: 'success' | 'error' } | null>(null)
  const actions = useMemo(() => ({ openAdd: () => setAdding(true) }), [])
  const collecting = isStarting || !!run && ['queued', 'running', 'waiting_for_user'].includes(run.status)
  const requestedReturn: unknown = location.state?.returnTo
  const catalogSearch = location.pathname === '/cards' ? location.search
    : typeof requestedReturn === 'string' && /^\/cards(?:\?[^#]*)?$/.test(requestedReturn) ? requestedReturn.slice('/cards'.length) : ''
  const params = useMemo(() => new URLSearchParams(catalogSearch), [catalogSearch])
  const tags = useMemo(() => [...new Set((catalog.data?.cards ?? []).flatMap((card) => card.tags ?? []))], [catalog.data?.cards])

  async function openBrowser() {
    setBrowserError(null)
    setOpeningBrowser(true)
    try {
      await invoke('open_store_browser')
    } catch (error) {
      setBrowserError(String(error))
    } finally {
      setOpeningBrowser(false)
    }
  }

  function changeFilters(next: URLSearchParams) {
    const search = next.toString()
    void navigate(`/cards${search ? `?${search}` : ''}`, { replace: location.pathname === '/cards', flushSync: true })
  }

  return (
    <CatalogActionsContext.Provider value={actions}>
      <div className="app-shell catalog-sidebar">
        <aside className="catalog-sidebar__sidebar" aria-label="Боковая панель">
          <div className="brand catalog-sidebar__brand"><BarChart3 aria-hidden="true" /><span>Price watch</span></div>
          <div className="catalog-sidebar__scroll">
            <div className="catalog-sidebar__primary">
              <Button className="justify-start" onClick={actions.openAdd}><Plus data-icon="inline-start" />Добавить карточку</Button>
              <Button className="justify-start" variant="outline" disabled={collecting} onClick={() => start()}><RefreshCw data-icon="inline-start" />Обновить все цены</Button>
              {startError ? <Alert variant="destructive"><AlertDescription>{startError}</AlertDescription></Alert> : null}
              <Button className="justify-start" variant="outline" onClick={() => setCreatingGroup(true)}><FolderPlus data-icon="inline-start" />Создать группу</Button>
            </div>
            <div className="catalog-sidebar__filters"><CatalogFilters tags={tags} params={params} onChange={changeFilters} /></div>
          </div>
          <div className="catalog-sidebar__tools">
            {isDesktopMode ? <Button className="justify-start" size="sm" variant="ghost" disabled={collecting || openingBrowser} onClick={() => void openBrowser()}><Globe2 data-icon="inline-start" />Открыть Chrome</Button> : null}
            <ImportExportControls label="Импорт / экспорт" onStatus={(message, kind) => setTransferStatus({ message, kind })} />
            {isDesktopMode ? <BackgroundSettings /> : <span className="catalog-sidebar__mode">{apiModeLabel}</span>}
          </div>
        </aside>
        <div className="catalog-sidebar__workspace">
          <main className="main-content">
            {serviceError ? <Alert variant="destructive" className="m-4"><AlertDescription><span>Фоновые службы: {serviceError}</span><Button variant="ghost" type="button" onClick={() => void retryServices()}>Повторить запуск</Button></AlertDescription></Alert> : null}
            {browserError ? <Alert variant="destructive"><AlertDescription>Не удалось открыть Chrome: {browserError}</AlertDescription></Alert> : null}
            {transferStatus ? <Alert variant={transferStatus.kind === 'error' ? 'destructive' : 'default'} role={transferStatus.kind === 'error' ? 'alert' : 'status'}><AlertDescription>{transferStatus.message}</AlertDescription></Alert> : null}
            <Outlet />
          </main>
        </div>
        <ActiveCollectionPanel />
        <AddCardDrawer side="left" open={adding} onClose={() => setAdding(false)} />
        {creatingGroup ? <GroupDialog group={null} cards={catalog.data?.cards ?? []} onClose={() => setCreatingGroup(false)} /> : null}
      </div>
    </CatalogActionsContext.Provider>
  )
}
