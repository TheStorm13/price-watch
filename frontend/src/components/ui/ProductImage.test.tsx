import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { MarketplaceCard } from '../../types/domain'
import { ProductImage } from './ProductImage'

const card: MarketplaceCard = {
  id: 1, marketplace: 'ozon', externalId: '123', title: 'Товар', url: null,
  imageUrl: 'https://img.test/photo.jpg', isActive: true, isArchived: false,
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
})
