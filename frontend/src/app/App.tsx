import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'
import { RouterProvider } from 'react-router-dom'
import { configureDesktopApi, isDesktopMode, type DesktopApiConfig } from '../api/client'
import { DesktopRuntimeContext } from './desktopRuntime'
import { AppProviders, queryClient } from './providers'
import { router } from './router'

let startupPromise: Promise<DesktopApiConfig> | null = null

function startDesktopServices() {
  if (!startupPromise) {
    startupPromise = invoke<DesktopApiConfig>('ensure_services').finally(() => {
      startupPromise = null
    })
  }
  return startupPromise
}

function applyDesktopConfig(config: DesktopApiConfig) {
  if (configureDesktopApi(config)) {
    queryClient.removeQueries({ queryKey: ['thumbnails'] })
    void queryClient.invalidateQueries()
  }
}

function DesktopBootstrap({ children }: { children: ReactNode }) {
  const [error, setError] = useState<string | null>(null)
  const [ready, setReady] = useState(!isDesktopMode)
  const [attempt, setAttempt] = useState(0)
  const configRevision = useRef(0)

  const retryServices = useCallback(async () => {
    const revision = configRevision.current
    try {
      const config = await startDesktopServices()
      if (revision !== configRevision.current) return
      applyDesktopConfig(config)
      setError(null)
      setReady(true)
    } catch (reason) {
      if (revision === configRevision.current) setError(String(reason))
    }
  }, [])

  useEffect(() => {
    if (!isDesktopMode) return
    void retryServices()
  }, [attempt, retryServices])

  useEffect(() => {
    if (!isDesktopMode) return
    let active = true
    const subscriptions = Promise.all([
      listen<DesktopApiConfig>('services-changed', (event) => {
        if (!active) return
        configRevision.current += 1
        applyDesktopConfig(event.payload)
        setError(null)
        setReady(true)
      }),
      listen<string>('services-error', (event) => {
        if (!active) return
        configRevision.current += 1
        setError(event.payload)
      }),
    ]).catch((reason: unknown) => {
      if (active) setError(`Не удалось следить за состоянием служб: ${String(reason)}`)
      return []
    })
    const refreshOnReveal = () => {
      if (document.visibilityState === 'visible') void retryServices()
    }
    document.addEventListener('visibilitychange', refreshOnReveal)
    window.addEventListener('focus', refreshOnReveal)
    return () => {
      active = false
      void subscriptions.then((unlisten) => unlisten.forEach((stop) => stop()))
      document.removeEventListener('visibilitychange', refreshOnReveal)
      window.removeEventListener('focus', refreshOnReveal)
    }
  }, [retryServices])

  return (
    <DesktopRuntimeContext.Provider value={{ serviceError: error, retryServices }}>
      {ready ? children : (
        <main className="desktop-bootstrap">
          <div className="desktop-bootstrap__mark">PW</div>
          <h1>{error ? 'Не удалось запустить приложение' : 'Запускаем Price watch'}</h1>
          <p>{error ?? 'Поднимаем PostgreSQL и API, затем запускаем браузерный агент…'}</p>
          {error
            ? <Button onClick={() => { setError(null); setAttempt((value) => value + 1) }}>Повторить</Button>
            : <Skeleton className="size-8" />}
        </main>
      )}
    </DesktopRuntimeContext.Provider>
  )
}

export function App() {
  return <DesktopBootstrap><AppProviders><RouterProvider router={router} /></AppProviders></DesktopBootstrap>
}
