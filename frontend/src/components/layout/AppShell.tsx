import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { lazy, Suspense, useState } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { BarChart3, Globe2 } from 'lucide-react'
import { Link, Outlet } from 'react-router-dom'
import { apiModeLabel, isDesktopMode, isE2ETestMode } from '../../api/client'
import { ActiveCollectionPanel } from '../../features/collection/ActiveCollectionPanel'
import { useCollection } from '../../features/collection/CollectionProvider'
import { BackgroundSettings } from '../../features/background/BackgroundSettings'
import { useDesktopRuntime } from '../../app/desktopRuntime'

const SidebarDemo = import.meta.env.DEV ? lazy(() => import('../../features/sidebar-demo/SidebarDemo')) : null

export function AppShell() {
  const [sidebarDemo] = useState(() => import.meta.env.DEV && isE2ETestMode && !isDesktopMode && (
    import.meta.env.VITE_SIDEBAR_DEMO === 'true' || new URLSearchParams(window.location.search).get('sidebar') === '2'
  ))
  const { run, isStarting } = useCollection()
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

  if (sidebarDemo && SidebarDemo) return <Suspense fallback={null}><SidebarDemo><Outlet /></SidebarDemo></Suspense>

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
        <Outlet />
      </main>
      <ActiveCollectionPanel />
    </div>
  )
}
