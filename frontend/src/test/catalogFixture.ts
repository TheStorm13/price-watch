import { mockApi } from '../api/mockApi'
import type { TransferCard } from '../types/domain'

/** Populate only the isolated mock preview, using the same transfer contract as the UI. */
export async function installCatalogFixture() {
  const exported = await mockApi.exportCards()
  const at = new Date().toISOString()
  function sample(source: TransferCard, marketplace: string, article: string, title: string, tags: string[], price: string): TransferCard {
    return { ...source, marketplace, externalId: article, primaryExternalId: article, title, tags, url: null,
      variants: [{ ...source.variants[0], externalId: article, productTitle: title, url: null, updatedAt: at,
        history: [{ price, availability: 'in_stock', observedAt: at }] }] }
  }
  await Promise.all([
    mockApi.updateCard(1, { tags: ['Электроника', 'Для себя'] }),
    mockApi.updateCard(2, { tags: ['Электроника', 'Подарки'] }),
    mockApi.updateCard(3, { tags: ['Электроника'] }),
    mockApi.updateCard(4, { tags: ['Для дома'] }),
    mockApi.updateCard(5, { tags: [] }),
  ])
  await mockApi.importCards({ version: 3, cards: [
    sample(exported.cards[1], 'wildberries', '234567890', 'Наушники Sony WH-1000XM5', ['Электроника', 'Для себя'], '27990.00'),
    sample(exported.cards[3], 'aliexpress', '1005009876543210', 'Робот-пылесос Roborock Q8 Max', ['Для дома', 'Подарки'], '31990.00'),
  ] })
}
