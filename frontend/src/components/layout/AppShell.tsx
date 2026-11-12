import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { useEffect, useMemo, useState } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { BarChart3, FolderPlus, Globe2, Plus, RefreshCw, Settings2 } from 'lucide-react'
import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { apiModeLabel, isDesktopMode } from '../../api/client'
import { useCatalog } from '../../api/queries'
import { ActiveCollectionPanel } from '../../features/collection/ActiveCollectionPanel'
import { useCollectionActions } from '../../features/collection/CollectionProvider'
import { BackgroundSettings } from '../../features/background/BackgroundSettings'
import { useDesktopRuntime } from '../../app/desktopRuntime'
import { AddCardDrawer } from '../../features/cards/AddCardDrawer'
import { GroupDialog } from '../../features/cards/GroupDialog'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger } from '@/components/ui/dialog'
import { ImportExportControls } from '../../features/cards/ImportExportControls'
import { catalogTags } from '../../features/cards/catalogModel'
import { CatalogFilters } from '../../features/cards/CatalogFilters'
import { PurchaseSettingsPanel } from '../../features/purchase/PurchaseSettingsPanel'
import { TargetNotificationObserver } from '../../features/purchase/TargetNotificationObserver'
import { CatalogActionsContext } from './catalogActions'
import { useCatalogPreferences } from '../../features/cards/useCatalogPreferences'

export function AppShell() {
  const location = useLocation()
  const navigate = useNavigate()
  const { restoreTo, savedSearch, rememberSearch } = useCatalogPreferences()
  const catalog = useCatalog()
  const { collecting, start, startError } = useCollectionActions()
  const { serviceError, retryServices } = useDesktopRuntime()
  useEffect(() => {
    if (isDesktopMode && !serviceError && !restoreTo) {
      // This shell is mounted after the router has resolved its lazy route.
      // Native code queues opening requests until this committed screen exists.
      void invoke('frontend_ready', { failed: false }).catch(() => { void retryServices() })
    }
  }, [serviceError, retryServices, restoreTo])
  const [browserError, setBrowserError] = useState<string | null>(null)
  const [openingBrowser, setOpeningBrowser] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [adding, setAdding] = useState(false)
  const [creatingGroup, setCreatingGroup] = useState(false)
  const [transferStatus, setTransferStatus] = useState<{ message: string; kind: 'success' | 'error' } | null>(null)
  const actions = useMemo(() => ({ openAdd: () => setAdding(true) }), [])
  const requestedReturn: unknown = location.state?.returnTo
  const catalogSearch = location.pathname === '/cards' ? location.search
    : typeof requestedReturn === 'string' && /^\/cards(?:\?[^#]*)?$/.test(requestedReturn) ? requestedReturn.slice('/cards'.length) : savedSearch
  const params = useMemo(() => new URLSearchParams(catalogSearch), [catalogSearch])
  const tags = useMemo(() => catalogTags(catalog.data?.cards ?? []), [catalog.data?.cards])

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
    rememberSearch(next)
    const search = next.toString()
    void navigate(`/cards${search ? `?${search}` : ''}`, { replace: location.pathname === '/cards', flushSync: true })
  }

  if (restoreTo) return <Navigate to={restoreTo} replace state={location.state} />

  return (
    <CatalogActionsContext.Provider value={actions}>
      <div className="app-shell catalog-sidebar">
        <aside className="catalog-sidebar__sidebar" aria-label="Боковая панель">
          <div className="brand catalog-sidebar__brand"><BarChart3 aria-hidden="true" /><span>Price watch</span></div>
          <div className="catalog-sidebar__scroll">
            <div className="catalog-sidebar__primary">
              <Button className="justify-start" disabled={collecting} onClick={() => start()}><RefreshCw data-icon="inline-start" />Обновить все цены</Button>
              <Button className="justify-start" variant="outline" onClick={actions.openAdd}><Plus data-icon="inline-start" />Добавить товар</Button>
              {startError ? <Alert variant="destructive"><AlertDescription>{startError}</AlertDescription></Alert> : null}
              <Button className="justify-start" variant="outline" onClick={() => setCreatingGroup(true)}><FolderPlus data-icon="inline-start" />Создать группу</Button>
            </div>
            <div className="catalog-sidebar__filters"><CatalogFilters tags={tags} params={params} onChange={changeFilters} /></div>
          </div>
          <div className="catalog-sidebar__tools">
            {isDesktopMode ? <Button className="justify-start" variant="outline" disabled={collecting || openingBrowser} onClick={() => void openBrowser()}><Globe2 data-icon="inline-start" />Открыть Chrome</Button> : null}
            <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
              <DialogTrigger asChild><Button className="justify-start" variant="outline"><Settings2 data-icon="inline-start" />Настройки</Button></DialogTrigger>
              <DialogContent className="settings-panel" viewportCentered>
                <DialogHeader><DialogTitle>Настройки</DialogTitle><DialogDescription className="sr-only">Настройки приложения и перенос данных</DialogDescription></DialogHeader>
                <section className="settings-block" aria-labelledby="settings-updates">
                  <h2 id="settings-updates">Обновление цен</h2>
                  <p>Изменение периодичности — пока не реализовано.</p>
                  <p>Обновление цен всех вариантов — пока не реализовано.</p>
                  {isDesktopMode ? <BackgroundSettings /> : <p>Фоновое обновление и автозапуск доступны в desktop-приложении. {apiModeLabel}</p>}
                </section>
                <section className="settings-block" aria-labelledby="settings-relative">
                  <h2 id="settings-relative">Условия покупки</h2>
                  <PurchaseSettingsPanel />
                </section>
                <ImportExportControls onStatus={(message, kind) => { setTransferStatus({ message, kind }); if (kind === 'success') setSettingsOpen(false) }} />
              </DialogContent>
            </Dialog>
          </div>
        </aside>
        <div className="catalog-sidebar__workspace">
          <main className="main-content">
            {serviceError ? <Alert variant="destructive" className="m-4"><AlertDescription><span>Фоновые службы: {serviceError}</span><Button variant="ghost" type="button" onClick={() => void retryServices()}>Повторить запуск</Button></AlertDescription></Alert> : null}
            {browserError ? <Alert variant="destructive"><AlertDescription>Не удалось открыть Chrome: {browserError}</AlertDescription></Alert> : null}
            {transferStatus ? <Alert variant={transferStatus.kind === 'error' ? 'destructive' : 'default'} role={transferStatus.kind === 'error' ? 'alert' : 'status'}><AlertDescription>{transferStatus.message}</AlertDescription></Alert> : null}
            <TargetNotificationObserver />
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
