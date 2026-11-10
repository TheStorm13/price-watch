import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { invoke } from '@tauri-apps/api/core'
import { AppShell } from './AppShell'

const state = vi.hoisted(() => ({
  run: null as null | { status: string }, isStarting: false,
  serviceError: null as string | null, retryServices: vi.fn(),
}))
vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }))
vi.mock('../../api/client', () => ({ isDesktopMode: true, apiModeLabel: 'Desktop' }))
vi.mock('../../api/queries', () => ({ useCatalog: () => ({ data: { cards: [], groups: [] } }) }))
vi.mock('../../features/collection/CollectionProvider', () => ({ useCollectionActions: () => ({ ...state, collecting: state.isStarting || !!state.run && ['queued', 'running', 'waiting_for_user'].includes(state.run.status), start: vi.fn() }) }))
vi.mock('../../app/desktopRuntime', () => ({ useDesktopRuntime: () => state }))
vi.mock('../../features/background/BackgroundSettings', () => ({ BackgroundSettings: () => <button>Настройки</button> }))
vi.mock('../../features/collection/ActiveCollectionPanel', () => ({ ActiveCollectionPanel: () => <div data-testid="progress" /> }))
vi.mock('../../features/cards/AddCardDrawer', () => ({ AddCardDrawer: () => null }))
vi.mock('../../features/cards/GroupDialog', () => ({ GroupDialog: () => null }))
vi.mock('../../features/cards/ImportExportControls', () => ({ ImportExportControls: () => null }))

function renderShell() {
  return render(<MemoryRouter initialEntries={['/cards/1']}><Routes><Route element={<AppShell />}><Route path="cards/:id" element={<h1>Товар</h1>} /></Route></Routes></MemoryRouter>)
}
beforeEach(() => { vi.mocked(invoke).mockResolvedValue(undefined) })
afterEach(() => { cleanup(); vi.clearAllMocks(); state.run = null; state.isStarting = false; state.serviceError = null })

it('uses the actual Chrome command, blocks double launch and reports launch errors in details', async () => {
  let fail!: (reason: Error) => void
  vi.mocked(invoke).mockImplementation(command => command === 'open_store_browser' ? new Promise((_, reject) => { fail = reject }) : Promise.resolve())
  renderShell()
  const button = screen.getByRole('button', { name: 'Открыть Chrome' })
  await userEvent.setup().click(button)
  expect(invoke).toHaveBeenCalledWith('open_store_browser')
  expect(button).toBeDisabled()
  fail(new Error('Chrome недоступен'))
  expect(await screen.findByRole('alert')).toHaveTextContent('Chrome недоступен')
  await waitFor(() => expect(button).toBeEnabled())
  expect(screen.getByRole('heading', { name: 'Товар' })).toBeInTheDocument()
})

it('disables Chrome and refresh while collection is waiting for the user', () => {
  state.run = { status: 'waiting_for_user' }
  renderShell()
  expect(screen.getByRole('button', { name: 'Открыть Chrome' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Обновить все цены' })).toBeDisabled()
  expect(screen.getAllByTestId('progress')).toHaveLength(1)
})

it('retains service recovery action in the permanent shell', async () => {
  state.serviceError = 'API недоступен'
  renderShell()
  expect(screen.getByRole('alert')).toHaveTextContent('API недоступен')
  await userEvent.setup().click(screen.getByRole('button', { name: 'Повторить запуск' }))
  expect(state.retryServices).toHaveBeenCalledOnce()
})

it('signals native readiness only after the product screen has committed', () => {
  vi.mocked(invoke).mockImplementation(command => {
    if (command === 'frontend_ready') expect(screen.getByRole('heading', { name: 'Товар' })).toBeInTheDocument()
    return Promise.resolve()
  })
  renderShell()
  expect(invoke).toHaveBeenCalledWith('frontend_ready', { failed: false })
})
