import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { invoke } from '@tauri-apps/api/core'
import { DesktopRuntimeContext } from '../../app/desktopRuntime'
import { BackgroundSettings } from './BackgroundSettings'

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('background settings', () => {
  it('loads, enables, and disables login startup', async () => {
    const invokeMock = vi.mocked(invoke)
    invokeMock.mockResolvedValueOnce({ enabled: false, serviceError: null })
      .mockResolvedValueOnce({ enabled: true, serviceError: null })
      .mockResolvedValueOnce({ enabled: false, serviceError: null })
    const user = userEvent.setup()
    render(<BackgroundSettings />)
    const toggle = await screen.findByRole('checkbox', { name: 'Запускать при входе в систему' })
    await waitFor(() => expect(toggle).toBeEnabled())
    expect(toggle).not.toBeChecked()

    await user.click(toggle)
    await waitFor(() => expect(toggle).toBeChecked())
    expect(invokeMock).toHaveBeenCalledWith('set_background_enabled', { enabled: true })

    await user.click(toggle)
    await waitFor(() => expect(toggle).not.toBeChecked())
    expect(invokeMock).toHaveBeenCalledWith('set_background_enabled', { enabled: false })
  })

  it('keeps the selected state and displays an error when registration fails', async () => {
    const invokeMock = vi.mocked(invoke)
    invokeMock.mockResolvedValueOnce({ enabled: false, serviceError: null })
      .mockRejectedValueOnce('Не удалось зарегистрировать автозапуск')
    const user = userEvent.setup()
    render(<BackgroundSettings />)
    const toggle = await screen.findByRole('checkbox', { name: 'Запускать при входе в систему' })
    await waitFor(() => expect(toggle).toBeEnabled())

    await user.click(toggle)
    expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось зарегистрировать автозапуск')
    expect(toggle).not.toBeChecked()
  })

  it('removes a service failure after the runtime recovers', async () => {
    vi.mocked(invoke).mockResolvedValue({ enabled: true, serviceError: null })
    const retryServices = vi.fn(async () => {})
    const { rerender } = render(
      <DesktopRuntimeContext.Provider value={{ serviceError: 'API недоступен', retryServices }}>
        <BackgroundSettings />
      </DesktopRuntimeContext.Provider>,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('API недоступен')

    rerender(
      <DesktopRuntimeContext.Provider value={{ serviceError: null, retryServices }}>
        <BackgroundSettings />
      </DesktopRuntimeContext.Provider>,
    )
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
