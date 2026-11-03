import { fireEvent, render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { TrackedCardView } from '../../types/domain'
import { ProductImage } from './ProductImage'

const card: TrackedCardView = {
  id: 1, marketplace: 'ozon', externalId: '123', title: 'Товар', url: null,
  imageUrl: 'https://img.test/photo.jpg', dealsEnabled: true,
  currentPrice: null, currentAvailability: null, lastObservedAt: null,
  createdAt: '2026-01-01T00:00:00Z', updatedAt: '2026-01-01T00:00:00Z',
}

describe('ProductImage', () => {
  it('shows the primary product photo inside the existing thumbnail', () => {
    const { container } = render(<ProductImage card={card} />)

    expect(container.querySelector('.product-placeholder')).toBeTruthy()
    expect(container.querySelector('img')).toHaveAttribute('src', card.imageUrl)
    expect(container.querySelector('img')).toHaveAttribute('loading', 'lazy')
  })

  it('keeps the initial when the connector has no photo', () => {
    const { container } = render(<ProductImage card={{ ...card, imageUrl: null }} />)

    expect(container.querySelector('.product-placeholder > span')?.textContent).toBe('Т')
    expect(container.querySelector('img')).toBeNull()
  })

  it('gives the detail photo a label and loads it eagerly', () => {
    const { getByRole } = render(<ProductImage card={card} alt="Фото товара: Товар" eager />)

    expect(getByRole('img', { name: 'Фото товара: Товар' })).toHaveAttribute('loading', 'eager')
  })
  it('restores a photo after the previous variant image failed', () => {
    const { container, rerender } = render(<ProductImage card={card} />)
    fireEvent.error(container.querySelector('img')!)
    expect(container.querySelector('.product-placeholder')).not.toHaveClass('product-placeholder--with-image')
    rerender(<ProductImage card={{ ...card, imageUrl: 'https://img.test/next.webp' }} />)
    expect(container.querySelector('.product-placeholder')).toHaveClass('product-placeholder--with-image')
    expect(container.querySelector('img')).not.toHaveStyle({ display: 'none' })
    rerender(<ProductImage card={{ ...card, imageUrl: null }} />)
    expect(container.querySelector('img')).toBeNull()
  })

})
