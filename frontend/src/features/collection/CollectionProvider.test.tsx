import { act, render, screen, cleanup } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, expect, it, vi } from 'vitest'
import type { CollectionRun, CatalogSnapshot } from '../../types/domain'
import { CollectionProvider, useCollection, useCollectionCommands, useCollectionActions } from './CollectionProvider'
import { api } from '../../api/client'
import { queryKeys, useCatalog } from '../../api/queries'

vi.mock('../../api/client', () => ({ isDesktopMode: false, api: {
  getCatalog: vi.fn(), getRun: vi.fn(), listRuns: vi.fn(), startRun: vi.fn(), retryRun: vi.fn(), continueRun: vi.fn(),
} }))
function Observer() {
  const state = useCollection()
  return <span data-testid="run">{state.run?.id ?? 'closed'}</span>
}
afterEach(() => { cleanup(); vi.useRealTimers(); vi.resetAllMocks(); localStorage.clear() })
it('does not render command consumers for thirty progress updates', async () => {
  vi.useFakeTimers()
  localStorage.setItem('price-watch-active-run', '99')
  const run: CollectionRun = {id:99,status:'running',totalCount:100,successCount:0,failureCount:0,
    current:null,challenge:null,startedAt:new Date().toISOString(),finishedAt:null,
    retryableCount:0,retryScopeIncomplete:false,diagnosticsStatus:'complete'}
  vi.mocked(api.getRun).mockResolvedValue(run)
  vi.mocked(api.listRuns).mockResolvedValue([run])
  let renders=0
  function Commands() { const commands=useCollectionCommands(); renders++; return <button onClick={()=>commands.start()}>Start</button> }
  const client=new QueryClient({defaultOptions:{queries:{retry:false}}})
  render(<QueryClientProvider client={client}><CollectionProvider><Commands /><Observer /></CollectionProvider></QueryClientProvider>)
  await act(async()=>{await vi.advanceTimersByTimeAsync(20)})
  const before=renders
  for(let i=1;i<=30;i++) await act(async()=>{
    client.setQueryData(queryKeys.run(99),{...run,successCount:i})
    await vi.advanceTimersByTimeAsync(2)
  })
  expect(renders).toBe(before)
  cleanup();client.clear()
})
it.each(['completed', 'completed_with_errors', 'failed'] as const)(
  'refreshes an active catalog after %s, independently of panel dismissal', async (status) => {
    vi.useFakeTimers()
    localStorage.setItem('price-watch-active-run', '99')
    const run: CollectionRun = { id: 99, status: 'running', totalCount: 1, successCount: 0, failureCount: 0,
      current: null, challenge: null, startedAt: new Date().toISOString(), finishedAt: null,
      retryableCount: 0, diagnosticsStatus: 'complete', retryScopeIncomplete: false }
    vi.mocked(api.getRun).mockResolvedValue(run)
    vi.mocked(api.listRuns).mockResolvedValue([])
    let finishCatalog!: (catalog: CatalogSnapshot) => void
    vi.mocked(api.getCatalog).mockImplementation(() => new Promise((resolve) => { finishCatalog = resolve }))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 15_000 } } })
    const previousUpdate = Date.now()
    client.setQueryData(queryKeys.catalog, { cards: [], groups: [], deals: [] })
    function Catalog() {
      const { isFetching } = useCatalog()
      return <span data-testid="catalog">{isFetching ? 'loading' : 'ready'}</span>
    }
    render(<QueryClientProvider client={client}><CollectionProvider><Observer /><Catalog /></CollectionProvider></QueryClientProvider>)
    await act(async () => { await vi.advanceTimersByTimeAsync(20) })
    expect(api.getCatalog).not.toHaveBeenCalled()
    await act(async () => {
      client.setQueryData(queryKeys.run(99), { ...run, status, finishedAt: new Date().toISOString() })
      await vi.advanceTimersByTimeAsync(20)
    })
    expect(api.getCatalog).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId('catalog')).toHaveTextContent('loading')
    if (status === 'completed') {
      await act(async () => { await vi.advanceTimersByTimeAsync(2_100) })
      expect(screen.getByTestId('run')).toHaveTextContent('closed')
    }
    const fresh: CatalogSnapshot = { cards: [], groups: [], deals: [] }
    await act(async () => { finishCatalog(fresh); await vi.advanceTimersByTimeAsync(20) })
    expect(screen.getByTestId('catalog')).toHaveTextContent('ready')
    expect(client.getQueryData(queryKeys.catalog)).toEqual(fresh)
    expect(client.getQueryState(queryKeys.catalog)!.dataUpdatedAt).toBeGreaterThan(previousUpdate)
    expect(api.getCatalog).toHaveBeenCalledTimes(1)
    cleanup(); client.clear()
  },
)

it('ignores saved notification queues and does not fetch an inactive catalog for notifications', async () => {
  vi.useFakeTimers()
  localStorage.setItem('price-watch-deal-notifications', JSON.stringify({ version: 2, pending: [98], processed: 0, prices: {} }))
  localStorage.setItem('price-watch-notified-run', '97')
  localStorage.setItem('price-watch-notified-prices', '{}')
  vi.mocked(api.listRuns).mockResolvedValue([])
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><CollectionProvider><Observer /></CollectionProvider></QueryClientProvider>)
  await act(async () => { await vi.advanceTimersByTimeAsync(35_000) })
  expect(api.getCatalog).not.toHaveBeenCalled()
  expect(screen.getByTestId('run')).toHaveTextContent('closed')
  cleanup(); client.clear()
})

it('exposes continuation failure, disables duplicate requests, and clears failure on retry', async () => {
  const { fireEvent, waitFor } = await import('@testing-library/react')
  const run: CollectionRun = { id: 99, status: 'waiting_for_user', totalCount: 5, successCount: 1, failureCount: 0,
    current: null, challenge: null, startedAt: new Date().toISOString(), finishedAt: null,
    retryableCount: 0, diagnosticsStatus: 'complete', retryScopeIncomplete: false }
  localStorage.setItem('price-watch-active-run', '99')
  vi.mocked(api.getRun).mockResolvedValue(run)
  vi.mocked(api.listRuns).mockResolvedValue([run])
  let resume!: (value: CollectionRun) => void
  vi.mocked(api.continueRun).mockRejectedValueOnce(new Error('Продолжение недоступно'))
    .mockImplementationOnce(() => new Promise((resolve) => { resume = resolve }))
  function Controls() {
    const state = useCollection()
    return <><button disabled={state.isContinuing} onClick={state.continueRun}>Продолжить</button><span role="status">{state.continueError}</span></>
  }
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><CollectionProvider><Controls /></CollectionProvider></QueryClientProvider>)
  await waitFor(() => expect(api.getRun).toHaveBeenCalled())
  fireEvent.click(screen.getByRole('button', { name: 'Продолжить' }))
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Продолжение недоступно'))
  fireEvent.click(screen.getByRole('button', { name: 'Продолжить' }))
  await waitFor(() => expect(screen.getByRole('button')).toBeDisabled())
  fireEvent.click(screen.getByRole('button'))
  expect(api.continueRun).toHaveBeenCalledTimes(2)
  expect(screen.getByRole('status')).toBeEmptyDOMElement()
  await act(async () => resume({ ...run, status: 'running' }))
  await waitFor(() => expect(screen.getByRole('button')).toBeEnabled())
  expect(screen.getByRole('status')).toBeEmptyDOMElement()
  cleanup(); client.clear()
})

it('isolates action consumers from counters but updates locks for every run state', async () => {
 vi.useFakeTimers()
 localStorage.setItem('price-watch-active-run','99')
 const run:CollectionRun={id:99,status:'queued',totalCount:100,successCount:0,failureCount:0,current:null,challenge:null,
   startedAt:new Date().toISOString(),finishedAt:null,retryableCount:0,retryScopeIncomplete:false,diagnosticsStatus:'complete'}
 vi.mocked(api.getRun).mockResolvedValue(run)
 vi.mocked(api.listRuns).mockResolvedValue([])
 let renders=0
 function Actions(){const state=useCollectionActions();renders++;return <button disabled={state.collecting}>Refresh</button>}
 const client=new QueryClient({defaultOptions:{queries:{retry:false}}})
 render(<QueryClientProvider client={client}><CollectionProvider><Actions/><Observer/></CollectionProvider></QueryClientProvider>)
 await act(async()=>{await vi.advanceTimersByTimeAsync(20)})
 expect(screen.getByRole('button')).toBeDisabled()
 const before=renders
 for(const status of ['running','waiting_for_user'] as const) await act(async()=>{
   client.setQueryData(queryKeys.run(99),{...run,status,successCount:2});await vi.advanceTimersByTimeAsync(20)
 })
 expect(renders).toBe(before)
 expect(screen.getByRole('button')).toBeDisabled()
 await act(async()=>{client.setQueryData(queryKeys.run(99),{...run,status:'completed'});await vi.advanceTimersByTimeAsync(20)})
 expect(screen.getByRole('button')).toBeEnabled()
 expect(renders).toBe(before+1)
 cleanup();client.clear()
})

it('publishes pending and start errors through the action boundary', async () => {
 const {fireEvent,waitFor}=await import('@testing-library/react')
 vi.mocked(api.listRuns).mockResolvedValue([])
 let fail!:(reason:Error)=>void
 vi.mocked(api.startRun).mockImplementation(()=>new Promise((_resolve,reject)=>{fail=reject}))
 function Actions(){const state=useCollectionActions();return <><button disabled={state.collecting} onClick={()=>state.start()}>Refresh</button><span role="status">{state.startError}</span></>}
 const client=new QueryClient({defaultOptions:{queries:{retry:false}}})
 render(<QueryClientProvider client={client}><CollectionProvider><Actions/></CollectionProvider></QueryClientProvider>)
 fireEvent.click(screen.getByRole('button'))
 await waitFor(()=>expect(screen.getByRole('button')).toBeDisabled())
 await act(async()=>fail(new Error('Start failed')))
 await waitFor(()=>expect(screen.getByRole('button')).toBeEnabled())
 expect(screen.getByRole('status')).toHaveTextContent('Start failed')
 cleanup();client.clear()
})
