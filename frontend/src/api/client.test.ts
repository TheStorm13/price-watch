import { afterEach, describe, expect, it, vi } from 'vitest'

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
  vi.resetModules()
})

describe('desktop API client', () => {
  it('uses the runtime address and session token', async () => {
    vi.stubEnv('VITE_DESKTOP_MODE', 'true')
    const fetchMock = vi.fn().mockResolvedValue(new Response('[]', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    const { api, configureDesktopApi } = await import('./client')

    configureDesktopApi({ baseUrl: 'http://127.0.0.1:49123', token: 'session-token' })
    await api.listCards()

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:49123/api/cards',
      expect.objectContaining({
        headers: expect.objectContaining({ 'X-Price-Watch-Token': 'session-token' }),
      }),
    )
  })
})
