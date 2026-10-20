import { useState } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { BarChart3, Globe2 } from 'lucide-react'
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
        <Link className="brand" to="/cards"><BarChart3 aria-hidden="true" /><span>Price Watch</span></Link>
        <div className="app-header__actions">
          <span className="app-header__mode">{apiModeLabel}</span>
          {isDesktopMode ? <BackgroundSettings /> : null}
          {isDesktopMode ? (
            <button
              className="app-header__browser-button"
              type="button"
              disabled={collecting || openingBrowser}
              onClick={() => void openBrowser()}
            >
              <Globe2 aria-hidden="true" /><span>Открыть Chrome</span>
            </button>
          ) : null}
        </div>
      </header>
      <main className="main-content">
        {serviceError ? <div className="desktop-service-error" role="alert"><span>Фоновые службы: {serviceError}</span><button type="button" onClick={() => void retryServices()}>Повторить запуск</button></div> : null}
        {browserError ? <p className="app-header__browser-error" role="alert">Не удалось открыть Chrome: {browserError}</p> : null}
        {dealNotice ? <div className="deal-notice" role="status"><span>Найдено выгодных предложений: {dealNotice}</span><Link to="/cards?deals=1" onClick={dismissDealNotice}>Посмотреть</Link><button type="button" onClick={dismissDealNotice} aria-label="Закрыть уведомление">×</button></div> : null}
        <Outlet />
      </main>
      <ActiveCollectionPanel />
    </div>
  )
}
