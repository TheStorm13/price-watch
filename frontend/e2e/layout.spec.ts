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
const layoutRun = { id:999, retryableCount:layoutMode==='errors'?4:0, retryScopeIncomplete:false, status:layoutMode.startsWith('waiting')?'waiting_for_user':layoutMode==='errors'?'completed_with_errors':layoutMode==='completed'?'completed':'running', totalCount:5, successCount:layoutMode==='completed'?5:1, failureCount:layoutMode==='errors'?4:0, current:{cardId:1,marketplace:'ozon',externalId:'1604900984'}, startedAt:new Date().toISOString(), finishedAt:layoutMode==='errors'||layoutMode==='completed'?new Date().toISOString():null, challenge:layoutMode.startsWith('waiting')?{type:'browser_verification',message:layoutMode==='waiting-long'?'Завершите проверку в открывшемся Chrome. '.repeat(30):'Завершите проверку в Chrome'}:null };
mockApi.getRun = async (_id, includeErrors) => ({...layoutRun,errors:includeErrors?Array.from({length:8},(_,i)=>({cardId:i+1,marketplace:'ozon',externalId:String(i+1),message:'Не удалось получить страницу товара. '.repeat(8),traceback:'Ошибка сбора\\n'.repeat(25)})):null});
mockApi.listRuns = async () => [];
` })
  })
}

test('панель обновления растёт с сообщением и сохраняет доступными ошибки и действия', async ({ page }) => {
  await panelFixture(page)
  for (const width of [1024, 1440]) {
    await page.setViewportSize({ width, height: width === 1024 ? 700 : 900 })
    const heights: number[] = []
    for (const mode of ['running', 'waiting', 'waiting-long', 'errors']) {
      await page.goto(`/cards?layout=${mode}`)
      const panel = page.getByLabel('Состояние обновления цен')
      await expect(panel).toBeVisible()
      if (mode === 'errors') {
        await panel.getByText('Показать ошибки', { exact: true }).click()
        await panel.getByText('Технические подробности', { exact: true }).first().click()
        await expect(panel.getByRole('button', { name: 'Повторить неудавшиеся и оставшиеся' })).toBeEnabled()
      }
      const box = (await panel.boundingBox())!
      heights.push(box.height)
      expect(box.y).toBeGreaterThanOrEqual(0)
      expect(box.y + box.height).toBeLessThanOrEqual(width === 1024 ? 700 : 900)
      const progress = panel.getByLabel('Прогресс обновления цен')
      await expect(progress).toBeVisible()
      const footer = panel.locator('[data-slot=card-footer]')
      await expect(footer).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)')
      await expect(footer).toHaveCSS('border-top-width', '0px')
      await expect(footer).toHaveCSS('box-shadow', 'none')
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
        await panel.getByRole('button', { name: 'Повторить неудавшиеся и оставшиеся' }).scrollIntoViewIfNeeded()
        await expect(panel.getByRole('button', { name: 'Повторить неудавшиеся и оставшиеся' })).toBeInViewport()
      }
    }
    expect(heights[1]).toBeGreaterThan(heights[0])
    expect(heights[2]).toBeGreaterThan(heights[1])
    expect(heights[3]).toBeGreaterThan(heights[0])
  }
})

test('панель изменения доступна в desktop-окне, ошибки тегов не теряют черновик', async ({ page }) => {
  for (const width of [1024, 1440]) {
    await page.setViewportSize({ width, height: 700 })
    await page.goto('/cards/1')
    await roundedEnds(page.getByRole('radiogroup', { name: 'Период истории' }))
    await page.getByRole('button', { name: 'Изменить', exact:true }).click()
    const panel=page.getByRole('dialog',{name:'Изменить товар'})
    const input=panel.getByLabel('Теги (до двух, через запятую)',{exact:true})
    await expect(input).toBeVisible()
    await input.fill('раз, два, три')
    await panel.getByRole('button',{name:'Сохранить',exact:true}).click()
    await expect(panel).toContainText('не больше 2')
    await expect(input).toHaveValue('раз, два, три')
    await input.fill('кухня, подарок')
    await panel.getByRole('button',{name:'Сохранить',exact:true}).click()
    await expect(panel).toHaveCount(0)
    await expect(page.getByRole('button',{name:'Изменить',exact:true})).toBeFocused()
    await page.getByRole('radio',{name:'7 дней'}).click()
    await roundedEnds(page.getByRole('radiogroup',{name:'Период истории'}))
  }
})

test('завершённый сбор со старой очередью не показывает уведомление', async ({ page }) => {
  await panelFixture(page)
  await page.addInitScript(() => {
    localStorage.setItem('price-watch-deal-notifications', JSON.stringify({ version: 2, pending: [999], processed: 0, prices: {} }))
    localStorage.setItem('price-watch-notified-run', '998')
    localStorage.setItem('price-watch-notified-prices', '{}')
  })
  await page.goto('/cards?layout=completed')
  await expect(page.getByText('Цены обновлены')).toBeVisible()
  await expect(page.locator('.cards-table__product')).toHaveCount(5)
  await expect(page.getByText('Цены обновлены')).toBeHidden({ timeout: 4_000 })
  await expect(page.getByText('Найдено выгодных предложений:', { exact: false })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Закрыть уведомление' })).toHaveCount(0)
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
