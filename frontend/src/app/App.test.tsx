import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { invoke } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }))
vi.mock('@tauri-apps/api/event', () => ({ listen: vi.fn() }))
vi.mock('react-router-dom', () => ({ RouterProvider: () => <div>Интерфейс готов</div> }))
vi.mock('./router', () => ({ router: {} }))
vi.mock('./providers', () => ({
  AppProviders: ({ children }: { children: ReactNode }) => children,
  queryClient: { removeQueries: vi.fn(), invalidateQueries: vi.fn() },
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
  vi.resetModules()
})

describe('desktop runtime connection', () => {
  it('keeps startup empty, then reveals a committed recoverable error', async () => {
    vi.stubEnv('VITE_DESKTOP_MODE', 'true')
    vi.mocked(listen).mockResolvedValue(() => {})
    let rejectStartup!: (reason: Error) => void
    vi.mocked(invoke).mockImplementation(command => command === 'ensure_services'
      ? new Promise((_, reject) => { rejectStartup = reject })
      : Promise.resolve(undefined as any))
    const { App } = await import('./App')
    const view = render(<App />)
    expect(view.container).toBeEmptyDOMElement()
    expect(invoke).not.toHaveBeenCalledWith('frontend_ready', expect.anything())
    await act(async () => rejectStartup(new Error('Synthetic service failure')))
    expect(screen.getByRole('alert')).toHaveTextContent('Synthetic service failure')
    expect(screen.getByRole('button', { name: 'Повторить' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Завершить работу' })).toBeVisible()
    expect(invoke).toHaveBeenCalledWith('frontend_ready', { failed: true })
  })

  it('uses a new API address and token after a service event', async () => {
    vi.stubEnv('VITE_DESKTOP_MODE', 'true')
    const callbacks = new Map<string, (event: { payload: unknown }) => void>()
    vi.mocked(listen).mockImplementation(async (name, handler) => {
      callbacks.set(name, handler as (event: { payload: unknown }) => void)
      return () => { callbacks.delete(name) }
    })
    vi.mocked(invoke).mockResolvedValue({ baseUrl: 'http://127.0.0.1:49123', token: 'first' })
    const fetchMock = vi.fn().mockImplementation(async () => new Response('[]', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    const { App } = await import('./App')
    const { api } = await import('../api/client')

    render(<App />)
    expect(await screen.findByText('Интерфейс готов')).toBeInTheDocument()
    await api.getCatalog()
    expect(fetchMock).toHaveBeenLastCalledWith('http://127.0.0.1:49123/api/catalog', expect.objectContaining({
      headers: expect.objectContaining({ 'X-Price-Watch-Token': 'first' }),
    }))

    callbacks.get('services-changed')?.({ payload: { baseUrl: 'http://127.0.0.1:49124', token: 'second' } })
    await api.getCatalog()
    expect(fetchMock).toHaveBeenLastCalledWith('http://127.0.0.1:49124/api/catalog', expect.objectContaining({
      headers: expect.objectContaining({ 'X-Price-Watch-Token': 'second' }),
    }))
  })

  it('refreshes the API connection when a hidden window is shown again', async () => {
    vi.stubEnv('VITE_DESKTOP_MODE', 'true')
    vi.mocked(listen).mockResolvedValue(() => {})
    let requests = 0
    vi.mocked(invoke).mockImplementation(async (command) => command === 'ensure_services' ? (++requests === 1 ? { baseUrl: 'http://127.0.0.1:49123', token: 'first' } : { baseUrl: 'http://127.0.0.1:49124', token: 'second' }) : undefined as any)
    const fetchMock = vi.fn().mockImplementation(async () => new Response('[]', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    const { App } = await import('./App')
    const { api } = await import('../api/client')

    render(<App />)
    expect(await screen.findByText('Интерфейс готов')).toBeInTheDocument()
    window.dispatchEvent(new Event('focus'))
    await waitFor(() => expect(vi.mocked(invoke).mock.calls.filter(([command]) => command === 'ensure_services')).toHaveLength(2))
    await waitFor(async () => {
      await api.getCatalog()
      expect(fetchMock).toHaveBeenLastCalledWith('http://127.0.0.1:49124/api/catalog', expect.objectContaining({
        headers: expect.objectContaining({ 'X-Price-Watch-Token': 'second' }),
      }))
    })
  })

  it('does not accept a stale startup reply after a service failure', async () => {
    vi.stubEnv('VITE_DESKTOP_MODE', 'true')
    const callbacks = new Map<string, (event: { payload: unknown }) => void>()
    vi.mocked(listen).mockImplementation(async (name, handler) => {
      callbacks.set(name, handler as (event: { payload: unknown }) => void)
      return () => { callbacks.delete(name) }
    })
    let resolveFirst!: (config: { baseUrl: string; token: string }) => void
    let requests = 0
    vi.mocked(invoke).mockImplementation((command) => command !== 'ensure_services' ? Promise.resolve(undefined as any) : ++requests === 1 ? new Promise((resolve) => { resolveFirst = resolve }) : Promise.resolve({ baseUrl: 'http://127.0.0.1:49124', token: 'working' } as any))
    const { App } = await import('./App')
    render(<App />)
    await waitFor(() => expect(callbacks.has('services-error')).toBe(true))

    act(() => callbacks.get('services-error')?.({ payload: 'API остановился' }))
    await act(async () => resolveFirst({ baseUrl: 'http://127.0.0.1:49123', token: 'stale' }))
    expect(screen.queryByText('Интерфейс готов')).not.toBeInTheDocument()
    expect(screen.getByText('API остановился')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Повторить' }))
    expect(await screen.findByText('Интерфейс готов')).toBeInTheDocument()
    expect(vi.mocked(invoke).mock.calls.filter(([command]) => command === 'ensure_services')).toHaveLength(2)
  })
})
