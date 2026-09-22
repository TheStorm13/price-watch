import { BarChart3, Play, Tags } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { apiModeLabel } from '../../api/client'
import { ActiveCollectionPanel } from '../../features/collection/ActiveCollectionPanel'

const links = [
  { to: '/cards', label: 'Карточки', icon: Tags },
  { to: '/runs', label: 'Запуски', icon: Play },
]

export function AppShell() {
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
        <div className="sidebar__mode">{apiModeLabel}</div>
      </aside>
      <main className="main-content"><Outlet /></main>
      <ActiveCollectionPanel />
    </div>
  )
}
