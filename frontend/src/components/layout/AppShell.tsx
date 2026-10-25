import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { useState } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { BarChart3, Globe2, X } from 'lucide-react'
import { Link, Outlet } from 'react-router-dom'
import { apiModeLabel, isDesktopMode } from '../../api/client'
import { ActiveCollectionPanel } from '../../features/collection/ActiveCollectionPanel'
import { useCollection } from '../../features/collection/CollectionProvider'
import { BackgroundSettings } from '../../features/background/BackgroundSettings'
import { useDesktopRuntime } from '../../app/desktopRuntime'

export function AppShell() {
  const { run, isStarting, dealNotice, dismissDealNotice } = useCollection()
  const { serviceError, retryServices } = useDesktopRuntime()
  const [browserError, setBrowserError] = useState<string | null>(null)
  const [openingBrowser, setOpeningBrowser] = useState(false)
  const collecting = isStarting || !!run && ['queued', 'running', 'waiting_for_user'].includes(run.status)

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

  return (
    <div className="app-shell">
      <header className="app-header">
        <Link className="brand" to="/cards"><BarChart3 aria-hidden="true" /><span>price-watch</span></Link>
        <div className="app-header__actions">
          <span className="app-header__mode">{apiModeLabel}</span>
          {isDesktopMode ? <BackgroundSettings /> : null}
          {isDesktopMode ? (
            <Button variant="outline"
              type="button"
              disabled={collecting || openingBrowser}
              onClick={() => void openBrowser()}
            >
              <Globe2 data-icon="inline-start" aria-hidden="true" /><span>Открыть Chrome</span>
            </Button>
          ) : null}
        </div>
      </header>
      <main className="main-content">
        {serviceError ? <Alert variant="destructive" className="mx-auto mt-4 max-w-[1440px]"><AlertDescription><span>Фоновые службы: {serviceError}</span><Button variant="ghost" type="button" onClick={() => void retryServices()}>Повторить запуск</Button></AlertDescription></Alert> : null}
        {browserError ? <Alert variant="destructive"><AlertDescription>Не удалось открыть Chrome: {browserError}</AlertDescription></Alert> : null}
        {dealNotice ? <Alert role="status" className="mx-auto mt-5 flex w-[calc(100%-4rem)] max-w-[1376px] items-center justify-between gap-4">
          <AlertDescription className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2">
            <span>Найдено выгодных предложений: {dealNotice}</span>
            <Button variant="link" asChild><Link to="/cards?deals=1" onClick={dismissDealNotice}>Посмотреть</Link></Button>
          </AlertDescription>
          <Button variant="ghost" size="icon-sm" type="button" onClick={dismissDealNotice} aria-label="Закрыть уведомление"><X /></Button>
        </Alert> : null}
        <Outlet />
      </main>
      <ActiveCollectionPanel />
    </div>
  )
}
