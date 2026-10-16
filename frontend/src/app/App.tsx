import { useEffect, useState, type ReactNode } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { RouterProvider } from 'react-router-dom'
import { configureDesktopApi, isDesktopMode, type DesktopApiConfig } from '../api/client'
import { AppProviders } from './providers'
import { router } from './router'

let startupPromise: Promise<void> | null = null

function startDesktopServices() {
  if (!startupPromise) {
    startupPromise = invoke<DesktopApiConfig>('ensure_services').then(configureDesktopApi).catch((error) => {
      startupPromise = null
      throw error
    })
  }
  return startupPromise
}

function DesktopBootstrap({ children }: { children: ReactNode }) {
  const [error, setError] = useState<string | null>(null)
  const [ready, setReady] = useState(!isDesktopMode)
  const [attempt, setAttempt] = useState(0)

  function migrateDatabase() {
    setError(null)
    invoke<DesktopApiConfig>('migrate_from_docker')
      .then((config) => {
        configureDesktopApi(config)
        startupPromise = Promise.resolve()
        setReady(true)
      })
      .catch((reason: unknown) => setError(String(reason)))
  }

  useEffect(() => {
    if (!isDesktopMode || ready) return
    let active = true
    startDesktopServices()
      .then(() => active && setReady(true))
      .catch((reason: unknown) => active && setError(String(reason)))
    return () => { active = false }
  }, [attempt, ready])

  if (ready) return children
  return (
    <main className="desktop-bootstrap">
      <div className="desktop-bootstrap__mark">PW</div>
      <h1>{error ? 'Не удалось запустить приложение' : 'Запускаем Price Watch'}</h1>
      <p>{error?.replace('LEGACY_DATABASE:', '') ?? 'Поднимаем PostgreSQL и API, затем запускаем браузерный агент…'}</p>
      {error
        ? error.includes('LEGACY_DATABASE:')
          ? <button className="button button--primary" onClick={migrateDatabase}>Перенести историю цен</button>
          : <button className="button button--primary" onClick={() => { setError(null); setAttempt((value) => value + 1) }}>Повторить</button>
        : <span className="desktop-bootstrap__loader" />}
    </main>
  )
}

export function App() {
  return <DesktopBootstrap><AppProviders><RouterProvider router={router} /></AppProviders></DesktopBootstrap>
}
