import { expect, test, type Locator, type Page } from '@playwright/test'

async function roundedEnds(group: Locator) {
  const buttons = group.getByRole('radio')
  await expect(buttons.first()).toHaveCSS('border-top-left-radius', '8px')
  await expect(buttons.first()).toHaveCSS('border-top-right-radius', '0px')
  await expect(buttons.last()).toHaveCSS('border-top-left-radius', '0px')
  await expect(buttons.last()).toHaveCSS('border-top-right-radius', '8px')
}

async function panelFixture(page: Page) {
  await page.addInitScript(() => localStorage.setItem('price-watch-active-run', '999'))
  await page.route('**/src/api/mockApi.ts', async (route) => {
    const response = await route.fetch()
    await route.fulfill({ response, body: await response.text() + `
const layoutMode = new URLSearchParams(location.search).get('layout') || 'running';
const layoutRun = { id:999, status:layoutMode.startsWith('waiting')?'waiting_for_user':layoutMode==='errors'?'completed_with_errors':layoutMode==='notice'?'completed':'running', totalCount:5, successCount:layoutMode==='notice'?5:1, failureCount:layoutMode==='errors'?4:0, current:{cardId:1,marketplace:'ozon',externalId:'1604900984'}, startedAt:new Date().toISOString(), finishedAt:layoutMode==='errors'||layoutMode==='notice'?new Date().toISOString():null, challenge:layoutMode.startsWith('waiting')?{type:'browser_verification',message:layoutMode==='waiting-long'?'Завершите проверку в открывшемся Chrome. '.repeat(30):'Завершите проверку в Chrome'}:null };
mockApi.getRun = async (_id, includeErrors) => ({...layoutRun,errors:includeErrors?Array.from({length:8},(_,i)=>({cardId:i+1,marketplace:'ozon',externalId:String(i+1),message:'Не удалось получить страницу товара. '.repeat(8),traceback:'Ошибка сбора\\n'.repeat(25)})):null});
mockApi.listRuns = async () => [];
if(layoutMode==='notice') mockApi.listDeals=async()=> (await mockApi.listCards()).map(card=>({card:{...card,currentPrice:100},savings:50,lastCollectionRunId:999}));
` })
  })
}

test('панель обновления растёт с сообщением и сохраняет доступными ошибки и действия', async ({ page }) => {
  await panelFixture(page)
  for (const width of [1024, 1440]) {
    await page.setViewportSize({ width, height: width === 1024 ? 768 : 900 })
    const heights: number[] = []
    for (const mode of ['running', 'waiting', 'waiting-long', 'errors']) {
      await page.goto(`/cards?layout=${mode}`)
      const panel = page.getByLabel('Состояние обновления цен')
      await expect(panel).toBeVisible()
      if (mode === 'errors') {
        await panel.getByText('Показать ошибки', { exact: true }).click()
        await panel.getByText('Технические подробности', { exact: true }).first().click()
        await expect(panel.getByRole('button', { name: 'Повторить ошибки' })).toBeEnabled()
      }
      const box = (await panel.boundingBox())!
      heights.push(box.height)
      expect(box.y).toBeGreaterThanOrEqual(0)
      expect(box.y + box.height).toBeLessThanOrEqual(width === 1024 ? 768 : 900)
      const progress = panel.getByLabel('Прогресс обновления цен')
      await expect(progress).toBeVisible()
      const progressBox = (await progress.boundingBox())!
      expect(progressBox.y + progressBox.height).toBeLessThan(box.y + box.height)
      if (mode.startsWith('waiting')) {
        const action = panel.getByRole('button', { name: 'Проверка пройдена' })
        await action.scrollIntoViewIfNeeded()
        const actionBox = (await action.boundingBox())!
        expect(actionBox.y).toBeGreaterThanOrEqual(box.y)
        expect(actionBox.y + actionBox.height).toBeLessThan(progressBox.y)
      }
      if (mode === 'errors') {
        const content = panel.locator('[data-slot=card-content]')
        expect(await content.evaluate((element) => element.scrollHeight > element.clientHeight)).toBe(true)
        await panel.getByRole('button', { name: 'Повторить ошибки' }).scrollIntoViewIfNeeded()
        await expect(panel.getByRole('button', { name: 'Повторить ошибки' })).toBeInViewport()
      }
      await page.screenshot({ path: `/tmp/price-watch-layout-panel-${mode}-${width}.png` })
    }
    expect(heights[1]).toBeGreaterThan(heights[0])
    expect(heights[2]).toBeGreaterThan(heights[1])
    expect(heights[3]).toBeGreaterThan(heights[0])
  }
})

test('поле тегов и кнопка выровнены с подсказкой и ошибкой, переключатели скруглены', async ({ page }) => {
  for (const width of [1024, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/cards/1')
    const input = page.getByLabel('Теги товара')
    const save = page.getByRole('button', { name: 'Сохранить теги' })
    const aligned = async () => {
      const [field, button] = await Promise.all([input.boundingBox(), save.boundingBox()])
      expect(Math.abs(field!.y + field!.height / 2 - button!.y - button!.height / 2)).toBeLessThan(1)
    }
    await expect(input).toBeVisible()
    await aligned()
    await roundedEnds(page.getByRole('radiogroup', { name: 'Период истории' }))
    await input.fill('раз, два, три')
    await save.click()
    await expect(page.getByRole('alert')).toBeVisible()
    await aligned()
    await page.screenshot({ path: `/tmp/price-watch-layout-tags-error-${width}.png` })
    await input.fill('кухня, подарок')
    await save.click()
    await expect(page.getByRole('alert')).toHaveCount(0)
    await aligned()
    await page.getByRole('radio', { name: '7 дней' }).click()
    await roundedEnds(page.getByRole('radiogroup', { name: 'Период истории' }))
    await page.screenshot({ path: `/tmp/price-watch-layout-details-${width}.png` })
  }
})

test('уведомление о пяти предложениях разделяет текст и действия и открывает фильтр', async ({ page }) => {
  await panelFixture(page)
  for (const width of [1024, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/cards?layout=notice')
    const notice = page.getByRole('status').filter({ hasText: 'Найдено выгодных предложений: 5' })
    await expect(notice).toBeVisible()
    const message = (await notice.getByText('Найдено выгодных предложений: 5', { exact: true }).boundingBox())!
    const link = (await notice.getByRole('link', { name: 'Посмотреть' }).boundingBox())!
    expect(link.x).toBeGreaterThanOrEqual(message.x + message.width + 12)
    await expect(notice.getByRole('button', { name: 'Закрыть уведомление' })).toBeVisible()
    await page.screenshot({ path: `/tmp/price-watch-layout-notice-${width}.png` })
    await notice.getByRole('link', { name: 'Посмотреть' }).click()
    await expect(page).toHaveURL(/deals=1/)
    await expect(notice).toBeHidden()
    await page.evaluate(() => { localStorage.removeItem('price-watch-notified-run'); localStorage.removeItem('price-watch-notified-prices') })
  }
  await page.goto('/cards?layout=notice')
  await page.getByRole('button', { name: 'Закрыть уведомление' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Найдено выгодных предложений:' })).toBeHidden()
})

test('цены и наличие читаемы, а переключатель каталога сохраняет скругления', async ({ page }) => {
  await page.goto('/cards')
  const table = page.locator('.cards-table')
  await expect(table).toBeVisible()
  for (const price of await table.locator('.price-cell').all()) expect(await price.evaluate((e) => parseFloat(getComputedStyle(e).fontSize))).toBeGreaterThanOrEqual(14)
  for (const status of await table.locator('.availability-status').all()) {
    expect(await status.evaluate((e) => parseFloat(getComputedStyle(e).fontSize))).toBeGreaterThanOrEqual(13)
    expect(await status.evaluate((e) => e.scrollHeight <= e.clientHeight)).toBe(true)
  }
  const views = page.getByRole('radiogroup', { name: 'Вид карточек' })
  await roundedEnds(views)
  await views.getByRole('radio', { name: 'Сетка' }).click()
  await roundedEnds(views)
  await views.getByRole('radio', { name: 'Список' }).click()
  await roundedEnds(views)
})
