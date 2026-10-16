import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { invoke } from '@tauri-apps/api/core'
import { api, isDesktopMode } from '../../api/client'
import { queryKeys, useRun } from '../../api/queries'
import type { CollectionRun } from '../../types/domain'

interface CollectionContextValue {
  run: CollectionRun | null
  isStarting: boolean
  startError: string | null
  start: (cardId?: number) => void
  openBrowser: () => void
  continueRun: () => void
  dismiss: () => void
  dealNotice: number | null
  dismissDealNotice: () => void
}

const CollectionContext = createContext<CollectionContextValue | null>(null)
const ACTIVE_RUN_KEY = 'price-watch-active-run'
const NOTIFIED_PRICES_KEY = 'price-watch-notified-prices'
const NOTIFIED_RUN_KEY = 'price-watch-notified-run'
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
  const [dealNotice, setDealNotice] = useState<number | null>(null)
  const seenLatestRun = useRef<number | null>(null)
  const runQuery = useRun(runId)
  const recentRuns = useQuery({ queryKey: ['recent-runs'], queryFn: api.listRuns, refetchInterval: 5_000 })

  useEffect(() => {
    const latest = recentRuns.data?.[0]
    if (!latest) return
    if (seenLatestRun.current === null) {
      seenLatestRun.current = latest.id
      const recent = Date.now() - Date.parse(latest.startedAt) < 2 * 60_000
      if (latest.id > (runId ?? 0) && (recent || ['queued', 'running', 'waiting_for_user'].includes(latest.status))) {
        setRunId(latest.id)
        window.localStorage.setItem(ACTIVE_RUN_KEY, String(latest.id))
      }
      return
    }
    if (latest.id > seenLatestRun.current) {
      seenLatestRun.current = latest.id
      setRunId(latest.id)
      window.localStorage.setItem(ACTIVE_RUN_KEY, String(latest.id))
    }
  }, [recentRuns.data, runId])

  const startMutation = useMutation({
    mutationFn: async (cardId?: number) => {
      if (isDesktopMode) await invoke('prepare_collection')
      return api.startRun(cardId)
    },
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
    client.invalidateQueries({ queryKey: queryKeys.deals })
  }, [client, isTerminal, run?.id])

  useEffect(() => {
    if (!isTerminal || !run || run.status === 'failed' || window.localStorage.getItem(NOTIFIED_RUN_KEY) === String(run.id)) return
    window.localStorage.setItem(NOTIFIED_RUN_KEY, String(run.id))
    void api.listDeals().then((deals) => {
      const previous = JSON.parse(window.localStorage.getItem(NOTIFIED_PRICES_KEY) || '{}') as Record<string, number>
      const fresh = deals.filter((deal) => deal.lastCollectionRunId === run.id && previous[String(deal.card.id)] !== deal.card.currentPrice)
      window.localStorage.setItem(NOTIFIED_PRICES_KEY, JSON.stringify(Object.fromEntries(
        deals.map((deal) => [deal.card.id, deal.card.currentPrice]),
      )))
      if (fresh.length) setDealNotice(fresh.length)
    }).catch(() => { /* The deals page still exposes API errors. */ })
  }, [isTerminal, run])

  const dismiss = useCallback(() => {
    setRunId(null)
    window.localStorage.removeItem(ACTIVE_RUN_KEY)
  }, [])

  const start = useCallback((cardId?: number) => {
    startMutation.mutate(cardId)
  }, [startMutation])

  const openBrowser = useCallback(() => openCollectorBrowser(), [])

  const value = useMemo<CollectionContextValue>(() => ({
    run,
    isStarting: startMutation.isPending,
    startError: startMutation.isError ? startMutation.error.message : null,
    start,
    openBrowser,
    continueRun: () => runId !== null && continueMutation.mutate(runId),
    dismiss,
    dealNotice,
    dismissDealNotice: () => setDealNotice(null),
  }), [continueMutation, dealNotice, dismiss, openBrowser, run, runId, start, startMutation.isPending, startMutation.isError, startMutation.error])

  return <CollectionContext.Provider value={value}>{children}</CollectionContext.Provider>
}

export function useCollection() {
  const value = useContext(CollectionContext)
  if (!value) throw new Error('useCollection должен использоваться внутри CollectionProvider')
  return value
}
