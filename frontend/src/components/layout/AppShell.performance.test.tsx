import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { AppShell } from './AppShell'
import { CollectionProvider } from '../../features/collection/CollectionProvider'
import { api } from '../../api/client'
import { queryKeys } from '../../api/queries'
import type { CollectionRun } from '../../types/domain'
const counters=vi.hoisted(()=>({filters:vi.fn(),drawer:vi.fn()}))
vi.mock('../../api/client',()=>({isDesktopMode:false,apiModeLabel:'Test',api:{getCatalog:vi.fn(),getRun:vi.fn(),listRuns:vi.fn()}}))
vi.mock('../../app/desktopRuntime',()=>({useDesktopRuntime:()=>({serviceError:null})}))
vi.mock('../../features/cards/CatalogFilters',()=>({CatalogFilters:()=>{counters.filters();return <span>Filters</span>}}))
vi.mock('../../features/cards/AddCardDrawer',()=>({AddCardDrawer:({open}:{open:boolean})=>{counters.drawer();return open?<input aria-label="Draft"/>:null}}))
vi.mock('../../features/collection/ActiveCollectionPanel',()=>({ActiveCollectionPanel:()=>null}))
afterEach(()=>{cleanup();localStorage.clear();vi.useRealTimers();vi.clearAllMocks()})
it('does not render sidebar filters or open/closed forms for progress-only updates',async()=>{
 vi.useFakeTimers();localStorage.setItem('price-watch-active-run','99')
 const run:CollectionRun={id:99,status:'running',totalCount:100,successCount:0,failureCount:0,current:null,challenge:null,
  startedAt:new Date().toISOString(),finishedAt:null,retryableCount:0,retryScopeIncomplete:false,diagnosticsStatus:'complete'}
 vi.mocked(api.getRun).mockResolvedValue(run);vi.mocked(api.listRuns).mockResolvedValue([])
 const client=new QueryClient({defaultOptions:{queries:{retry:false,staleTime:Infinity}}})
 client.setQueryData(queryKeys.catalog,{cards:[],groups:[],deals:[]})
 render(<QueryClientProvider client={client}><CollectionProvider><MemoryRouter><Routes><Route element={<AppShell/>}><Route path="/" element={<p>Catalog</p>}/></Route></Routes></MemoryRouter></CollectionProvider></QueryClientProvider>)
 await act(async()=>{await vi.advanceTimersByTimeAsync(20)})
 for(const open of [false,true]) {
  if(open){fireEvent.click(screen.getByRole('button',{name:'Добавить товар'}));const input=screen.getByLabelText('Draft');fireEvent.change(input,{target:{value:'draft text'}});input.focus()}
  const before=[counters.filters.mock.calls.length,counters.drawer.mock.calls.length]
  for(let i=1;i<=30;i++) await act(async()=>{client.setQueryData(queryKeys.run(99),{...run,successCount:i+(open?30:0)});await vi.advanceTimersByTimeAsync(2)})
  expect([counters.filters.mock.calls.length,counters.drawer.mock.calls.length]).toEqual(before)
  if(open){expect(screen.getByLabelText('Draft')).toHaveValue('draft text');expect(screen.getByLabelText('Draft')).toHaveFocus()}
 }
 cleanup();client.clear()
})
