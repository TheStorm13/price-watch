import { StrictMode } from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, Navigate, Outlet, RouterProvider, useLocation, useNavigate } from 'react-router-dom'
import { readCatalogPreferences, writeCatalogPreferences } from './catalogPreferences'
import { useCatalogPreferences } from './useCatalogPreferences'

const renders: string[] = []
function Catalog() {
  const location = useLocation()
  renders.push(location.search)
  return <p>Каталог</p>
}
function Shell() {
  const location = useLocation()
  const navigate = useNavigate()
  const { restoreTo, rememberSearch } = useCatalogPreferences()
  if (restoreTo) return <Navigate to={restoreTo} replace />
  return <>
    <output>{location.pathname}{location.search}</output>
    <button onClick={() => { rememberSearch(new URLSearchParams()); void navigate('/cards') }}>Сбросить из панели</button>
    <Outlet />
  </>
}
function mount(path: string) {
  const router = createMemoryRouter([{ Component: Shell, children: [
    { path: 'cards', Component: Catalog }, { path: 'cards/:id', element: <p>Детали</p> },
  ] }], { initialEntries: [path] })
  render(<StrictMode><RouterProvider router={router} /></StrictMode>)
  return router
}
beforeEach(() => { localStorage.clear(); renders.length = 0 })
afterEach(() => { cleanup(); vi.restoreAllMocks() })

it('restores once before rendering catalog, preserving service parameters and hash', async () => {
  writeCatalogPreferences({ catalogSearch: 'stock=1&sort=price-desc&view=grid' })
  const router = mount('/cards?fixture=large#catalog')
  await waitFor(() => expect(router.state.location.search).toContain('stock=1'))
  expect(router.state.location.search).toContain('fixture=large')
  expect(router.state.location.hash).toBe('#catalog')
  expect(renders.every((value) => value.includes('stock=1'))).toBe(true)
  await act(() => router.navigate('/cards?view=grid'))
  expect(readCatalogPreferences().catalogSearch).toBe('view=grid')
  cleanup()
  const restarted = mount('/cards')
  await waitFor(() => expect(restarted.state.location.search).toBe('?view=grid'))
})

it('honors an explicit link as a complete set, including explicit defaults', () => {
  writeCatalogPreferences({ catalogSearch: 'stock=1&view=grid&sort=price-desc' })
  mount('/cards?participationFirst=1')
  expect(renders.every((value) => value === '?participationFirst=1')).toBe(true)
  expect(readCatalogPreferences().catalogSearch).toBe('')
})

it('does not restore after reset, detail return or history navigation to blank search', async () => {
  writeCatalogPreferences({ catalogSearch: 'stock=1' })
  const router = mount('/cards')
  await waitFor(() => expect(router.state.location.search).toBe('?stock=1'))
  await act(() => router.navigate('/cards/1'))
  await act(() => router.navigate('/cards'))
  expect(router.state.location.search).toBe('')
  await act(() => router.navigate('/cards?tags='))
  await act(() => router.navigate(-1))
  expect(router.state.location.search).toBe('')
  await act(() => router.navigate(1))
  expect(router.state.location.search).toBe('?tags=')
  expect(readCatalogPreferences().catalogSearch).toBe('tags=')
})

it('allows clearing filters from details opened directly, without resurrecting saved filters', async () => {
  writeCatalogPreferences({ catalogSearch: 'stock=1' })
  const router = mount('/cards/1')
  fireEvent.click(screen.getByRole('button', { name: 'Сбросить из панели' }))
  await waitFor(() => expect(router.state.location.pathname).toBe('/cards'))
  expect(router.state.location.search).toBe('')
  expect(readCatalogPreferences().catalogSearch).toBe('')
})

it('allows URL changes even when storage is unavailable', async () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('denied') })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('denied') })
  const router = mount('/cards')
  await act(() => router.navigate('/cards?stock=1'))
  expect(screen.getByText('Каталог')).toBeInTheDocument()
  expect(router.state.location.search).toBe('?stock=1')
})
