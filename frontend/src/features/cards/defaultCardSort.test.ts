import { expect, test } from 'vitest'
import type { MarketplaceCard } from '../../types/domain'
import { compareDefaultCards } from './defaultCardSort'

function card(id: number, availability: MarketplaceCard['currentAvailability'], price: number | null):
  Pick<MarketplaceCard, 'id' | 'currentAvailability' | 'currentPrice'> {
  return { id, currentAvailability: availability, currentPrice: price }
}

test('default order prioritizes availability, savings, then lower price', () => {
  const cards = [
    card(1, 'out_of_stock', null),
    card(2, 'in_stock', 500),
    card(3, 'in_stock', 100),
    card(4, 'in_stock', 300),
    card(5, 'unknown', null),
    card(6, null, null),
    card(7, 'in_stock', 50),
    card(8, 'unknown', 500),
  ]
  const savings = new Map([[2, 20], [3, 10], [4, 20]])

  expect(cards.toSorted((left, right) => compareDefaultCards(left, right, savings)).map((item) => item.id))
    .toEqual([4, 2, 3, 7, 1, 8, 5, 6])
})
