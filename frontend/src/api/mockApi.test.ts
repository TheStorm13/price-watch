import { describe, expect, it, vi } from 'vitest'
import { mockApi } from './mockApi'

describe('mock deal list', () => {
  it('does not wait seven days after the card was created', async () => {
    const card = await mockApi.getCard(1)
    const clock = vi.spyOn(Date, 'now').mockReturnValue(Date.parse(card.createdAt) + 6 * 86_400_000)
    try {
      expect((await mockApi.listDeals()).map((deal) => deal.card.id)).toContain(card.id)
    } finally {
      clock.mockRestore()
    }
  })
})
