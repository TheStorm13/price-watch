import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, isDemoMode, isDesktopMode } from '../../api/client'
import { queryKeys, useRun } from '../../api/queries'
import type { CollectionRun } from '../../types/domain'

interface CollectionContextValue {
  run: CollectionRun | null
  isStarting: boolean
  start: (cardId?: number) => void
  openBrowser: () => void
  continueRun: () => void
  dismiss: () => void
}

const CollectionContext = createContext<CollectionContextValue | null>(null)
const ACTIVE_RUN_KEY = 'price-watch-active-run'
const COLLECTOR_BROWSER_URL = '/browser/vnc.html?autoconnect=true&resize=scale&path=browser/websockify'

function openCollectorBrowser() {
  const browserWindow = window.open(COLLECTOR_BROWSER_URL, 'price-watch-collector-browser')
  browserWindow?.focus()
}

function initialRunId() {
  const stored = window.localStorage.getItem(ACTIVE_RUN_KEY)
  return stored ? Number(stored) : null
}

export function CollectionProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient()
  const [runId, setRunId] = useState<number | null>(initialRunId)
  const runQuery = useRun(runId)

  const startMutation = useMutation({
    mutationFn: api.startRun,
    onSuccess: (run) => {
      setRunId(run.id)
      window.localStorage.setItem(ACTIVE_RUN_KEY, String(run.id))
      client.setQueryData(queryKeys.run(run.id), run)
      client.invalidateQueries({ queryKey: queryKeys.runs })
    },
  })

  const continueMutation = useMutation({
    mutationFn: (id: number) => api.continueRun(id),
    onSuccess: (run) => client.setQueryData(queryKeys.run(run.id), run),
  })

  const run = runQuery.data ?? null
  const isTerminal = run ? ['completed', 'completed_with_errors', 'failed'].includes(run.status) : false

  useEffect(() => {
    if (!isTerminal) return
    client.invalidateQueries({ queryKey: queryKeys.cards })
    client.invalidateQueries({ queryKey: queryKeys.runs })
  }, [client, isTerminal])

  const dismiss = useCallback(() => {
    setRunId(null)
    window.localStorage.removeItem(ACTIVE_RUN_KEY)
  }, [])

  const start = useCallback((cardId?: number) => {
    // Popup blockers allow window.open only while handling the user's click.
    if (!isDemoMode && !isDesktopMode) openCollectorBrowser()
    startMutation.mutate(cardId)
  }, [startMutation])

  const openBrowser = useCallback(() => openCollectorBrowser(), [])

  const value = useMemo<CollectionContextValue>(() => ({
    run,
    isStarting: startMutation.isPending,
    start,
    openBrowser,
    continueRun: () => runId !== null && continueMutation.mutate(runId),
    dismiss,
  }), [continueMutation, dismiss, openBrowser, run, runId, start, startMutation.isPending])

  return <CollectionContext.Provider value={value}>{children}</CollectionContext.Provider>
}

export function useCollection() {
  const value = useContext(CollectionContext)
  if (!value) throw new Error('useCollection должен использоваться внутри CollectionProvider')
  return value
}
