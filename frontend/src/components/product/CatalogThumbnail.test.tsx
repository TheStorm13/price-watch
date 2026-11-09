import { act, render, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../api/client'
import { thumbnailConfig } from '../../api/thumbnailConfig'
import { CatalogThumbnail } from './CatalogThumbnail'

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
    const first = render(<CatalogThumbnail card={card} />, { wrapper })
    await waitFor(() => expect(first.container.querySelector('img')).toHaveAttribute('src', 'blob:thumbnail-1'))
    expect(api.getThumbnail).toHaveBeenCalledWith(1, expect.any(AbortSignal))
    first.unmount()
    expect(revoked).toHaveBeenCalledWith('blob:thumbnail-1')
    const second = render(<CatalogThumbnail card={card} />, { wrapper })
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
    const view = render(<CatalogThumbnail card={card} />, { wrapper })
    view.rerender(<CatalogThumbnail card={{ ...card, imageUrl: 'https://cdn.test/new' }} />)
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
    const view = render(<CatalogThumbnail card={{ ...card, imageUrl: null }} />, { wrapper })
    expect(api.getThumbnail).not.toHaveBeenCalled()
    view.rerender(<CatalogThumbnail card={card} />)
    await waitFor(() => expect(client.getQueryCache().getAll().some((q) => q.state.status === 'error')).toBe(true))
    expect(view.container.querySelector('img')).toBeNull()
    expect(view.container.querySelector('.product-placeholder')?.textContent).toBe('Ф')
    view.unmount()
  })
})
