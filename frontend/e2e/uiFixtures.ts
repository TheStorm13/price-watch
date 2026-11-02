import { expect, type Page } from '@playwright/test'

export async function uiFixture(page: Page) {
  await page.clock.setFixedTime(new Date('2026-10-29T12:00:00Z'))
  await page.route('**/src/api/mockApi.ts*', async (route) => {
    const response = await route.fetch()
    await route.fulfill({ response, body: await response.text() + `
const fixtureCatalog = mockApi.getCatalog.bind(mockApi), fixtureCard = mockApi.getCard.bind(mockApi);
const fixtureDecorate = card => ({ ...card,
  title: card.id === 1 ? 'Короткое название' : card.id === 2 ? 'Очень длинное название товара с описанием комплектации и характеристик выбранной модели' : card.id === 4 ? null : card.title,
  tags: card.id === 2 ? ['Первый очень длинный тег товара', 'Второй длинный тег'] : card.id === 3 ? ['Один тег'] : [],
  dealsEnabled: card.id !== 2 && card.id !== 5,
  imageUrl: card.id <= 2 ? 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="'+(card.id===1?200:400)+'" height="'+(card.id===1?400:200)+'"><rect width="100%" height="100%" rx="24" fill="'+(card.id===1?'#dbeafe':'#dcfce7')+'"/><circle cx="50%" cy="50%" r="60" fill="'+(card.id===1?'#2563eb':'#15803d')+'"/></svg>') : null,
});
mockApi.getCatalog = async () => {
  const snapshot = await fixtureCatalog();
  return {...snapshot,cards:snapshot.cards.map(fixtureDecorate),groups:snapshot.groups.map(g=>({...g,representativeCard:g.representativeCard?fixtureDecorate(g.representativeCard):null}))};
};
mockApi.getCard = async id => fixtureDecorate(await fixtureCard(id));
` })
  })
  await page.goto('/cards')
  await expect(page.getByText('Короткое название', { exact: true }).first()).toBeVisible()
}
