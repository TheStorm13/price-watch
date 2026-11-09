import { act, render, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../api/client'
import { thumbnailConfig } from '../../api/thumbnailConfig'
import { PreparedProductImage } from './PreparedProductImage'

vi.mock('../../api/client', () => ({ api: { getThumbnail: vi.fn() } }))
const card = { id: 1, title: 'Фото', imageUrl: 'https://cdn.test/original' }
let created: ReturnType<typeof vi.fn>, revoked: ReturnType<typeof vi.fn>
beforeEach(() => {
  vi.clearAllMocks()
  let index = 0
  created = vi.fn(() => `blob:thumbnail-${++index}`)
  revoked = vi.fn()
  vi.stubGlobal('URL', { createObjectURL: created, revokeObjectURL: revoked })
})
afterEach(() => vi.unstubAllGlobals())

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
  return { client, wrapper }
}

describe('catalog thumbnails', () => {
  it('uses the prepared blob, reuses cached data and releases each object URL', async () => {
    vi.mocked(api.getThumbnail).mockResolvedValue(new Blob(['png'], { type: 'image/png' }))
    const { wrapper } = setup()
    const first = render(<PreparedProductImage card={card} />, { wrapper })
    await waitFor(() => expect(first.container.querySelector('img')).toHaveAttribute('src', 'blob:thumbnail-1'))
    expect(api.getThumbnail).toHaveBeenCalledWith(1, { profile: 'list', scale: 1, variantId: undefined }, expect.any(AbortSignal))
    first.unmount()
    expect(revoked).toHaveBeenCalledWith('blob:thumbnail-1')
    const second = render(<PreparedProductImage card={card} />, { wrapper })
    await waitFor(() => expect(second.container.querySelector('img')).toHaveAttribute('src', 'blob:thumbnail-2'))
    expect(api.getThumbnail).toHaveBeenCalledTimes(1)
    second.unmount()
    expect(revoked).toHaveBeenCalledWith('blob:thumbnail-2')
  })

  it('ignores a late response after the source changes and resets on API configuration change', async () => {
    let finish!: (value: Blob) => void
    vi.mocked(api.getThumbnail).mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
      .mockResolvedValue(new Blob(['new']))
    const { wrapper } = setup()
    const view = render(<PreparedProductImage card={card} />, { wrapper })
    view.rerender(<PreparedProductImage card={{ ...card, imageUrl: 'https://cdn.test/new' }} />)
    await waitFor(() => expect(view.container.querySelector('img')).toHaveAttribute('src', 'blob:thumbnail-1'))
    await act(async () => finish(new Blob(['old'])))
    expect(created).toHaveBeenCalledTimes(1)
    act(() => thumbnailConfig.changed())
    await waitFor(() => expect(api.getThumbnail).toHaveBeenCalledTimes(3))
    await waitFor(() => expect(view.container.querySelector('img')).toHaveAttribute('src', 'blob:thumbnail-2'))
    expect(revoked).toHaveBeenCalledWith('blob:thumbnail-1')
    view.unmount()
  })

  it('shows the existing placeholder for absent and failed images', async () => {
    vi.mocked(api.getThumbnail).mockRejectedValue(new Error('image unavailable'))
    const { wrapper, client } = setup()
    const view = render(<PreparedProductImage card={{ ...card, imageUrl: null }} />, { wrapper })
    expect(api.getThumbnail).not.toHaveBeenCalled()
    view.rerender(<PreparedProductImage card={card} />)
    await waitFor(() => expect(client.getQueryCache().getAll().some((q) => q.state.status === 'error')).toBe(true))
    expect(view.container.querySelector('img')).toBeNull()
    expect(view.container.querySelector('.product-placeholder')?.textContent).toBe('Ф')
    view.unmount()
  })

  it('requests the physical size after repeated monitor or zoom changes and releases old URLs', async () => {
    let changed: (() => void) | undefined
    const remove = vi.fn()
    vi.stubGlobal('matchMedia', vi.fn(() => ({
      addEventListener: (_event: string, listener: () => void) => { changed = listener },
      removeEventListener: remove,
    })))
    vi.stubGlobal('devicePixelRatio', 1)
    vi.mocked(api.getThumbnail).mockImplementation(async (_id, size) => new Blob([String(size)]))
    const { wrapper } = setup()
    const view = render(<PreparedProductImage card={card} />, { wrapper })
    for (const [index, ratio] of [1, 1.25, 1.5, 2, 3].entries()) {
      act(() => { vi.stubGlobal('devicePixelRatio', ratio); changed?.() })
      await waitFor(() => expect(api.getThumbnail).toHaveBeenLastCalledWith(1, { profile: 'list', scale: ratio, variantId: undefined }, expect.any(AbortSignal)))
      await waitFor(() => expect(view.container.querySelector('img')).toHaveAttribute('src', `blob:thumbnail-${index + 1}`))
      if (index) expect(revoked).toHaveBeenCalledWith(`blob:thumbnail-${index}`)
    }
    view.unmount()
    expect(revoked).toHaveBeenCalledWith('blob:thumbnail-5')
    expect(remove).toHaveBeenCalled()
  })
})
