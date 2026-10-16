import { useState } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { BarChart3, Globe2, Play, Tags } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { apiModeLabel, isDesktopMode } from '../../api/client'
import { ActiveCollectionPanel } from '../../features/collection/ActiveCollectionPanel'
import { useCollection } from '../../features/collection/CollectionProvider'

const links = [
  { to: '/cards', label: 'Карточки', icon: Tags },
  { to: '/runs', label: 'Запуски', icon: Play },
]

export function AppShell() {
  const { run, isStarting, dealNotice, dismissDealNotice } = useCollection()
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
      <aside className="sidebar">
        <div className="brand"><BarChart3 aria-hidden="true" /><span>Price Watch</span></div>
        <nav className="sidebar__nav" aria-label="Основная навигация">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} className={({ isActive }) => `nav-link ${isActive ? 'is-active' : ''}`}>
              <Icon aria-hidden="true" /><span>{label}</span>
            </NavLink>
          ))}
        </nav>
        {isDesktopMode ? (
          <div className="sidebar__browser">
            <button
              className="sidebar__browser-button"
              type="button"
              disabled={collecting || openingBrowser}
              onClick={() => void openBrowser()}
            >
              <Globe2 aria-hidden="true" /><span>Открыть Chrome</span>
            </button>
            {browserError ? <p className="sidebar__browser-error" role="alert">{browserError}</p> : null}
          </div>
        ) : null}
        <div className="sidebar__mode">{apiModeLabel}</div>
      </aside>
      <main className="main-content">
        {dealNotice ? <div className="deal-notice" role="status"><span>Найдено выгодных предложений: {dealNotice}</span><NavLink to="/cards?deals=1" onClick={dismissDealNotice}>Посмотреть</NavLink><button type="button" onClick={dismissDealNotice} aria-label="Закрыть уведомление">×</button></div> : null}
        <Outlet />
      </main>
      <ActiveCollectionPanel />
    </div>
  )
}
