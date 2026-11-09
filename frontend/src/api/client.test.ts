import { afterEach, describe, expect, it, vi } from 'vitest'

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
  vi.resetModules()
})

describe('desktop API client', () => {
  it('rejects live requests before the desktop API is configured', async () => {
    vi.stubEnv('VITE_DESKTOP_MODE', 'false')
    vi.stubEnv('VITE_E2E_TEST_MODE', 'false')
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const { api } = await import('./client')

    await expect(api.getCatalog()).rejects.toThrow('Локальный API ещё не запущен')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('uses the runtime address and session token', async () => {
    vi.stubEnv('VITE_DESKTOP_MODE', 'true')
    const fetchMock = vi.fn().mockResolvedValue(new Response('[]', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    const { api, configureDesktopApi } = await import('./client')

    configureDesktopApi({ baseUrl: 'http://127.0.0.1:49123', token: 'session-token' })
    await api.getCatalog()
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:49123/api/catalog',
      expect.objectContaining({
        headers: expect.objectContaining({ 'X-Price-Watch-Token': 'session-token' }),
      }),
    )
  })
  it('loads authenticated binary images with cancellation and resets config revision', async () => {
    vi.stubEnv('VITE_E2E_TEST_MODE', 'false')
    const fetchMock = vi.fn().mockResolvedValue(new Response('png', { headers: { 'Content-Type': 'image/png' } }))
    vi.stubGlobal('fetch', fetchMock)
    const { api, configureDesktopApi } = await import('./client')
    const { thumbnailConfig } = await import('./thumbnailConfig')
    configureDesktopApi({ baseUrl: 'http://127.0.0.1:1234', token: 'secret' })
    const revision = thumbnailConfig.snapshot()
    expect(configureDesktopApi({ baseUrl: 'http://127.0.0.1:1234', token: 'secret' })).toBe(false)
    const signal = new AbortController().signal
    expect(await api.getThumbnail(7, signal)).toBeInstanceOf(Blob)
    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:1234/api/cards/7/thumbnail', expect.objectContaining({
      signal, headers: expect.objectContaining({ 'X-Price-Watch-Token': 'secret' }),
    }))
    configureDesktopApi({ baseUrl: 'http://127.0.0.1:1234', token: 'new-secret' })
    expect(thumbnailConfig.snapshot()).toBe(revision + 1)
  })

})
