import { Button } from '@/components/ui/button'
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

  useEffect(() => {
    if (!isDesktopMode || ready || !error) return
    // Effects run after the DOM commits. Hidden WebViews may suspend animation frames.
    let active = true
    void invoke('frontend_ready', { failed: true }).catch((reason: unknown) => {
      if (active) setError(String(reason))
    })
    return () => { active = false }
  }, [ready, error])

  return (
    <DesktopRuntimeContext.Provider value={{ serviceError: error, retryServices }}>
      {ready ? children : error ? (
        <main className="desktop-startup-error">
          <h1>Не удалось запустить приложение</h1>
          <p role="alert">{error}</p>
          <div className="flex gap-2"><Button onClick={() => setAttempt((value) => value + 1)}>Повторить</Button>
          <Button variant="outline" onClick={() => void invoke('quit_app')}>Завершить работу</Button></div>
        </main>
      ) : null}
    </DesktopRuntimeContext.Provider>
  )
}

export function App() {
  return <DesktopBootstrap><AppProviders><RouterProvider router={router} /></AppProviders></DesktopBootstrap>
}
