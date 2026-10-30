import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { invoke } from '@tauri-apps/api/core'
import { api, isDesktopMode } from '../../api/client'
import { catalogOptions, queryKeys, useRun } from '../../api/queries'
import type { CollectionRun } from '../../types/domain'
import { DealNotifications } from './dealNotifications'

interface CollectionContextValue {
  run: CollectionRun | null
  isStarting: boolean
  startError: string | null
  start: (cardId?: number) => void
  isContinuing: boolean
  continueError: string | null
  continueRun: () => void
  retryErrors: () => void
  isRetrying: boolean
  retryError: string | null
  dismiss: () => void
  dealNotice: number | null
  dismissDealNotice: () => void
}

type CollectionCommands = Pick<CollectionContextValue, 'start' | 'isStarting' | 'startError'>
const CollectionCommandsContext = createContext<CollectionCommands | null>(null)
const CollectionContext = createContext<CollectionContextValue | null>(null)
const ACTIVE_RUN_KEY = 'price-watch-active-run'

function initialRunId() {
  const stored = window.localStorage.getItem(ACTIVE_RUN_KEY)
  const value = Number(stored)
  return Number.isSafeInteger(value) && value > 0 ? value : null
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
      client.invalidateQueries({ queryKey: ['recent-runs'] })
    },
  })

  const continueMutation = useMutation({
    mutationFn: (id: number) => api.continueRun(id),
    onSuccess: (run) => client.setQueryData(queryKeys.run(run.id), run),
  })

  const retryMutation = useMutation({
    mutationFn: async (id: number) => {
      if (isDesktopMode) await invoke('prepare_collection')
      return api.retryRun(id)
    },
    onSuccess: (nextRun) => {
      setRunId(nextRun.id)
      window.localStorage.setItem(ACTIVE_RUN_KEY, String(nextRun.id))
      client.setQueryData(queryKeys.run(nextRun.id), nextRun)
      client.invalidateQueries({ queryKey: ['recent-runs'] })
    },
  })

  const run = runQuery.data ?? null
  const isTerminal = run ? ['completed', 'completed_with_errors', 'failed'].includes(run.status) : false

  const notifications = useMemo(() => new DealNotifications(window.localStorage, async () => {
    // A pre-terminal request cannot acknowledge this run's notification work.
    await client.cancelQueries({ queryKey: queryKeys.catalog })
    return client.fetchQuery({ ...catalogOptions, staleTime: 0, retry: false })
  }, setDealNotice), [client])

  useEffect(() => {
    notifications.start()
    return () => notifications.stop()
  }, [notifications])

  useEffect(() => {
    if (!isTerminal || !run) return
    void client.invalidateQueries({ queryKey: queryKeys.cardRoot })
    void client.invalidateQueries({ queryKey: ['recent-runs'] })
    if (run.status === 'failed') void client.invalidateQueries({ queryKey: queryKeys.catalog })
    else notifications.enqueue(run.id)
  }, [client, isTerminal, run?.id, run?.status, notifications])

  const dismiss = useCallback(() => {
    if (runId !== null) seenLatestRun.current = Math.max(seenLatestRun.current ?? 0, runId)
    setRunId(null)
    window.localStorage.removeItem(ACTIVE_RUN_KEY)
  }, [runId])

  useEffect(() => {
    if (run?.status !== 'completed') return
    const timeout = window.setTimeout(dismiss, 2_000)
    return () => window.clearTimeout(timeout)
  }, [dismiss, run?.id, run?.status])

  const { mutate: startRun, isPending: isStarting, error: startReason } = startMutation
  const { mutate: continueRun, isPending: isContinuing, variables: continuingId, error: continueReason } = continueMutation
  const { mutate: retryRun, isPending: isRetrying, variables: retryingId, error: retryReason } = retryMutation
  const start = useCallback((cardId?: number) => startRun(cardId), [startRun])
  const resume = useCallback(() => { if (runId !== null && !isContinuing) continueRun(runId) }, [runId, isContinuing, continueRun])
  const retry = useCallback(() => { if (runId !== null) retryRun(runId) }, [runId, retryRun])
  const dismissNotice = useCallback(() => setDealNotice(null), [])
  const commands = useMemo(() => ({ start, isStarting, startError: startReason?.message ?? null }), [start, isStarting, startReason])

  const value = useMemo<CollectionContextValue>(() => ({
    ...commands, run, continueRun: resume, isContinuing: isContinuing && continuingId === runId,
    continueError: continuingId === runId ? continueReason?.message ?? null : null,
    retryErrors: retry, isRetrying, retryError: retryingId === runId ? retryReason?.message ?? null : null,
    dismiss, dealNotice, dismissDealNotice: dismissNotice,
  }), [commands, run, resume, isContinuing, continuingId, runId, continueReason, retry, isRetrying, retryingId, retryReason, dismiss, dealNotice, dismissNotice])

  return <CollectionCommandsContext.Provider value={commands}><CollectionContext.Provider value={value}>{children}</CollectionContext.Provider></CollectionCommandsContext.Provider>
}

export function useCollection() {
  const value = useContext(CollectionContext)
  if (!value) throw new Error('useCollection должен использоваться внутри CollectionProvider')
  return value
}

export function useCollectionCommands() {
  const value = useContext(CollectionCommandsContext)
  if (!value) throw new Error('useCollectionCommands должен использоваться внутри CollectionProvider')
  return value
}
