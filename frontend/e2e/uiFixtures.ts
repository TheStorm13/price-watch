import { expect, type Page } from '@playwright/test'

type RunStatus = 'running' | 'waiting_for_user' | 'completed_with_errors'

export async function uiFixture(page: Page, group = false, runStatus?: RunStatus) {
  await page.clock.setFixedTime(new Date('2026-10-29T12:00:00Z'))
  if (runStatus) await page.addInitScript(() => localStorage.setItem('price-watch-active-run', '999'))
  await page.route('**/src/api/mockApi.ts*', async (route) => {
    const response = await route.fetch()
    await route.fulfill({ response, body: await response.text() + `
const fixtureGroup = ${JSON.stringify(group)};
const fixtureStatus = ${JSON.stringify(runStatus ?? null)};
const fixtureCatalog = mockApi.getCatalog.bind(mockApi), fixtureCard = mockApi.getCard.bind(mockApi);
const fixtureDecorate = card => ({ ...card,
  title: card.id === 1 ? 'Короткое название' : card.id === 2 ? 'Очень длинное название товара с описанием комплектации и характеристик выбранной модели' : card.id === 4 ? null : card.title,
  tags: card.id === 2 ? ['Первый очень длинный тег товара', 'Второй длинный тег'] : card.id === 3 ? ['Один тег'] : [],
  dealsEnabled: card.id !== 2 && card.id !== 5,
  imageUrl: card.id <= 2 ? 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="'+(card.id===1?200:400)+'" height="'+(card.id===1?400:200)+'"><rect width="100%" height="100%" rx="24" fill="'+(card.id===1?'#dbeafe':'#dcfce7')+'"/><circle cx="50%" cy="50%" r="60" fill="'+(card.id===1?'#2563eb':'#15803d')+'"/></svg>') : null,
});
let fixtureInitialized = false;
mockApi.getCatalog = async () => {
  if (fixtureGroup && !fixtureInitialized) { fixtureInitialized=true; await mockApi.createGroup({name:'Сравнение моделей',tags:[],cardIds:[1,2]}); }
  const snapshot = await fixtureCatalog();
  return {...snapshot,cards:snapshot.cards.map(fixtureDecorate),groups:snapshot.groups.map(g=>({...g,representativeCard:g.representativeCard?fixtureDecorate(g.representativeCard):null}))};
};
mockApi.getCard = async id => fixtureDecorate(await fixtureCard(id));
if (fixtureStatus) {
  const fixtureRun={id:999,status:fixtureStatus,totalCount:5,successCount:1,failureCount:fixtureStatus==='completed_with_errors'?4:0,current:null,startedAt:new Date().toISOString(),finishedAt:fixtureStatus==='completed_with_errors'?new Date().toISOString():null,challenge:fixtureStatus==='waiting_for_user'?{type:'browser_verification',message:'Завершите проверку в открывшемся Chrome.'}:null,retryableCount:fixtureStatus==='completed_with_errors'?4:0,retryScopeIncomplete:false};
  mockApi.listRuns=async()=>[fixtureRun];
  mockApi.getRun=async()=>({...fixtureRun,errors:fixtureStatus==='completed_with_errors'?[{cardId:1,message:'Не удалось загрузить товар',marketplace:'ozon',externalId:'123'}]:null});
}
` })
  })
  await page.goto('/cards')
  await expect(page.getByText(group ? 'Сравнение моделей' : 'Короткое название', { exact: true }).first()).toBeVisible()
}
