import { Suspense } from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { CardsPage } from './CardsPage'
import { CatalogActionsContext } from '../../components/layout/catalogActions'
import { performanceData } from '../../test/performanceData'
const observed=vi.hoisted(()=>({renders:vi.fn(),snapshot:null as unknown,suspend:false}))
vi.mock('../../api/queries',()=>({useCatalog:()=>({data:observed.snapshot})}))
vi.mock('./BulkCardActions',()=>({BulkCardActions:()=>null}))
vi.mock('./GroupDialog',()=>({GroupDialog:()=>null}))
vi.mock('./CatalogResults',async()=>{
 const {memo}=await import('react')
 return {CatalogResults:memo(function Results({returnTo}:{returnTo:string}){
  observed.renders(returnTo)
  if(observed.suspend && returnTo.includes('q=')) throw new Promise(()=>{})
  return <div data-testid="results">{returnTo}</div>
 })}
})
afterEach(()=>{cleanup();observed.renders.mockClear();observed.suspend=false})
it('skips unchanged results during urgent input and retains coherent context while background work suspends',()=>{
 observed.snapshot=performanceData(100,'plain')
 const router=createMemoryRouter([{path:'/cards',element:<CatalogActionsContext.Provider value={{openAdd:()=>{}}}><Suspense fallback={<p>Loading</p>}><CardsPage/></Suspense></CatalogActionsContext.Provider>}],{initialEntries:['/cards']})
 render(<RouterProvider router={router}/>)
 expect(observed.renders).toHaveBeenCalledTimes(1)
 observed.renders.mockClear();observed.suspend=true
 fireEvent.change(screen.getByRole('textbox'),{target:{value:'Тест'}})
 expect(screen.getByRole('textbox')).toHaveValue('Тест')
 expect(screen.getByTestId('results')).toHaveTextContent('/cards')
 expect(observed.renders.mock.calls.length).toBeGreaterThan(0)
 // Background attempts are allowed; an urgent rerender with old context is wasted work.
 expect(observed.renders.mock.calls.every(([context])=>context.includes('q='))).toBe(true)
 expect(screen.queryByText('Loading')).not.toBeInTheDocument()
})
