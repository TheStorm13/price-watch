import { expect, test } from '@playwright/test'
import { readFile } from 'node:fs/promises'

test('основной desktop-сценарий', async ({ page }) => {
  const errors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text())
  })

  await page.setViewportSize({ width: 1536, height: 1024 })
  await page.goto('/cards')
  await expect(page).toHaveTitle('Price Watch')
  await expect(page.getByRole('heading', { name: 'Карточки' })).toBeVisible()
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toBeVisible()
  await page.screenshot({ path: '/tmp/price-watch-cards.png' })

  await page.getByRole('button', { name: 'Добавить карточку' }).click()
  await expect(page.getByRole('dialog', { name: 'Добавить карточку' })).toBeVisible()
  await page.waitForTimeout(250)
  await page.screenshot({ path: '/tmp/price-watch-drawer.png' })
  await page.getByRole('button', { name: 'Закрыть', exact: true }).click()

  await page.getByLabel('Поиск карточек').fill('Dyson')
  await expect(page.getByRole('row', { name: /Пылесос Dyson/ })).toBeVisible()
  await page.getByLabel('Поиск карточек').fill('')
  await page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ }).click()
  await expect(page).toHaveURL(/\/cards\/1/)
  await expect(page.getByRole('heading', { name: 'История цены' })).toBeVisible()
  await expect(page.getByText('72 990 ₽').first()).toBeVisible()
  await expect(page.getByRole('link', { name: 'Открыть на Ozon' })).toHaveAttribute('href', 'https://www.ozon.ru/product/1604900984')
  await page.getByRole('button', { name: /Действия с карточкой/ }).click()
  await expect(page.getByRole('menuitem', { name: 'Исключить из выгодных предложений' })).toBeVisible()
  await expect(page.getByRole('menuitem', { name: 'Удалить карточку' })).toBeVisible()
  await page.keyboard.press('Escape')
  await page.screenshot({ path: '/tmp/price-watch-detail.png' })
  expect(errors).toEqual([])
})

test('из каталога запускается сбор только выбранной карточки', async ({ page }) => {
  await page.goto('/cards')
  const row = page.getByRole('row', { name: /Наушники Apple AirPods Pro 2/ })
  await row.getByRole('button', { name: /Действия с карточкой/ }).click()
  await page.getByRole('menuitem', { name: 'Обновить только эту карточку' }).click()
  await expect(page.getByLabel('Состояние обновления цен')).toContainText('0 из 1')
  await page.getByRole('link', { name: 'Запуски' }).click()
  await expect(page.getByRole('row', { name: /#22/ }).locator('td').nth(6)).toHaveText('1')
})

test('компактный desktop 1024 px не имеет горизонтального overflow', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 })
  await page.goto('/cards')
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toBeVisible()
  const hasOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
  expect(hasOverflow).toBe(false)
  await page.goto('/cards/1')
  await expect(page.getByText('Разница', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
})

test('карточки переключаются между списком и сеткой из четырёх колонок', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 })
  await page.goto('/cards')
  const row = page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })
  await expect(row).toBeVisible()
  const rowHeight = await row.evaluate((element) => element.getBoundingClientRect().height)
  await page.getByRole('button', { name: 'Сетка' }).click()
  const grid = page.getByRole('list', { name: 'Отслеживаемые карточки маркетплейсов' })
  await expect(grid.locator('li')).toHaveCount(5)
  expect(await grid.evaluate((element) => getComputedStyle(element).gridTemplateColumns.split(' ').length)).toBe(4)
  await page.screenshot({ path: '/tmp/price-watch-grid.png' })
  await grid.locator('li').first().getByRole('button', { name: /Действия с карточкой/ }).click()
  await expect(page.getByRole('menuitem', { name: 'Исключить из выгодных предложений' })).toBeVisible()
  await page.keyboard.press('Escape')
  await page.getByRole('heading', { name: 'Карточки' }).click()
  await page.setViewportSize({ width: 1536, height: 900 })
  expect(await grid.evaluate((element) => getComputedStyle(element).gridTemplateColumns.split(' ').length)).toBe(4)
  await page.screenshot({ path: '/tmp/price-watch-grid-wide.png' })
  await page.reload()
  await expect(grid.locator('li')).toHaveCount(5)
  await grid.getByRole('link', { name: /Смартфон Samsung Galaxy S24/ }).click()
  await expect(page).toHaveURL(/\/cards\/1/)
  await page.setViewportSize({ width: 1024, height: 768 })
  await page.goto('/cards?view=grid')
  await page.getByRole('button', { name: 'Список' }).click()
  await expect(row).toBeVisible()
  expect(await row.evaluate((element) => element.getBoundingClientRect().height)).toBe(rowHeight)
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
})

test('экспорт и импорт объединяют карточки и историю', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 })
  await page.goto('/cards')
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Экспорт', exact: true }).click()
  const download = await downloadPromise
  const exportData = JSON.parse(await readFile(await download.path(), 'utf8'))
  expect(exportData.cards).toHaveLength(5)
  expect(exportData.cards[0].history[0]).toEqual(expect.objectContaining({
    price: expect.any(String), availability: expect.any(String), observedAt: expect.any(String),
  }))
  expect(exportData.cards[0]).not.toHaveProperty('isArchived')
  exportData.cards.push({
    marketplace: 'ozon', externalId: '9999911111', title: 'Тестовый импорт',
    url: null, isActive: true, isArchived: true, createdAt: new Date().toISOString(),
    history: [{ price: '123.00', availability: 'in_stock', observedAt: new Date().toISOString() }],
  })
  await page.getByRole('button', { name: 'Импорт', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Импорт карточек и истории' })
  await dialog.locator('input[type="file"]').setInputFiles({
    name: 'price-watch-export.json', mimeType: 'application/json',
    buffer: Buffer.from(JSON.stringify(exportData)),
  })
  await expect(dialog).toContainText('Добавлено карточек: 1, объединено: 5')
  await page.screenshot({ path: '/tmp/price-watch-import-preview.png' })
  await dialog.getByRole('button', { name: 'Импортировать' }).click()
  await expect(page.getByRole('row', { name: /Тестовый импорт/ })).toBeVisible()
  await expect(page.getByRole('row', { name: /Тестовый импорт/ })).toContainText('Не показывается в выгодных предложениях')
  await page.screenshot({ path: '/tmp/price-watch-imported.png' })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
})

test('меню карточки управляет показом в выгодных предложениях', async ({ page }) => {
  await page.goto('/cards')
  const row = page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })
  await row.getByRole('button', { name: /Действия с карточкой/ }).click()
  await expect(page.getByRole('menuitem', { name: 'Исключить из выгодных предложений' })).toBeVisible()
  await expect(page.getByRole('menuitem', { name: 'В архив' })).toHaveCount(0)
  await page.getByRole('menuitem', { name: 'Исключить из выгодных предложений' }).click()
  await expect(row.getByText('Не показывается в выгодных предложениях')).toBeVisible()

  await row.getByRole('button', { name: /Действия с карточкой/ }).click()
  await expect(page.getByRole('menuitem', { name: 'Показывать в выгодных предложениях' })).toBeVisible()
  await page.screenshot({ path: '/tmp/price-watch-card-actions.png' })
  await page.getByRole('menuitem', { name: 'Показывать в выгодных предложениях' }).click()
  await expect(row.getByText('Не показывается в выгодных предложениях')).toBeHidden()
})

test('исключённая карточка обновляется, но не попадает в выгодные предложения', async ({ page }) => {
  await page.goto('/deals')
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toBeVisible()

  await page.getByRole('link', { name: 'Карточки' }).click()
  const row = page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })
  await row.getByRole('button', { name: /Действия с карточкой/ }).click()
  await page.getByRole('menuitem', { name: 'Исключить из выгодных предложений' }).click()
  await expect(row).toContainText('Не показывается в выгодных предложениях')
  await page.getByLabel('Состояние').selectOption('excluded')
  await expect(row).toBeVisible()

  await page.getByRole('link', { name: 'Выгодные предложения' }).click()
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toHaveCount(0)
  await page.getByRole('link', { name: 'Карточки' }).click()
  await page.getByLabel('Состояние').selectOption('excluded')
  await row.getByRole('button', { name: /Действия с карточкой/ }).click()
  await page.getByRole('menuitem', { name: 'Обновить только эту карточку' }).click()
  await expect(page.getByLabel('Состояние обновления цен')).toContainText('0 из 1')
  await page.goto('/cards/1')
  await expect(page.getByRole('button', { name: 'Обновить эту карточку' })).toBeEnabled()
})

test('удаление карточки требует подтверждения', async ({ page }) => {
  await page.goto('/cards')
  const row = page.getByRole('row', { name: /Пылесос Dyson/ })

  await row.getByRole('button', { name: /Действия с карточкой/ }).click()
  await page.getByRole('menuitem', { name: 'Удалить карточку' }).click()
  const dialog = page.getByRole('alertdialog', { name: 'Удалить карточку?' })
  await expect(dialog).toContainText('вся история её цен будут удалены')
  await page.screenshot({ path: '/tmp/price-watch-delete-confirmation.png' })
  await dialog.getByRole('button', { name: 'Отмена' }).click()
  await expect(row).toBeVisible()

  await page.getByRole('menuitem', { name: 'Удалить карточку' }).click()
  await dialog.getByRole('button', { name: 'Удалить', exact: true }).click()
  await expect(row).toBeHidden()
})

test('запуск доходит до проверки и продолжается', async ({ page }) => {
  await page.goto('/cards')
  await page.getByRole('button', { name: 'Обновить цены' }).click()
  await expect(page.getByLabel('Состояние обновления цен')).toBeVisible()
  await expect(page.getByLabel('Состояние обновления цен')).toContainText('0 из 5')
  await expect(page.getByText('Требуется проверка Ozon')).toBeVisible({ timeout: 8_000 })
  await page.getByRole('button', { name: 'Проверка пройдена' }).click()
  await expect(page.getByText('Цены обновлены')).toBeVisible({ timeout: 8_000 })
  await expect(page.getByRole('status').filter({ hasText: 'Найдено выгодных предложений: 1' })).toBeVisible({ timeout: 5_000 })
})

test('детали карточки показывают середину диапазона и страницы истории', async ({ page }) => {
  await page.goto('/cards/1')
  await expect(page.getByText('Середина диапазона')).toBeVisible()
  await expect(page.getByText('77 240 ₽', { exact: true })).toBeVisible()
  await expect(page.getByText('Разница', { exact: true })).toBeVisible()
  await expect(page.getByText('8 500 ₽', { exact: true })).toBeVisible()
  await expect(page.getByLabel('График истории цены')).toBeVisible()
  await page.screenshot({ path: '/tmp/price-watch-chart.png' })
})

test('из списка запусков открываются подробности', async ({ page }) => {
  await page.goto('/runs')
  await page.getByRole('button', { name: '#21' }).click()
  await expect(page.getByRole('region', { name: 'Подробности запуска 21' })).toBeVisible()
  await expect(page.getByText('Ошибок в этом запуске нет.')).toBeVisible()
  await page.getByRole('button', { name: '#20' }).click()
  await expect(page.getByText('Не удалось получить страницу товара', { exact: true })).toBeVisible()
  await page.getByText('Технические подробности').click()
  await expect(page.getByText('MarketplaceUnavailable: Не удалось получить страницу товара')).toBeVisible()
})

test('одиночное измерение остаётся точкой на графике с масштабом вокруг цены', async ({ page }) => {
  await page.goto('/cards/2')
  const chart = page.getByLabel('График истории цены')
  await expect(chart).toBeVisible()
  await expect(chart.locator('.recharts-line-dot')).toHaveCount(1)
  await expect(chart.getByText('0', { exact: true })).toHaveCount(0)
})

test('дата обновления карточки новее первой сохранённой точки цены', async ({ page }) => {
  await page.goto('/cards')
  const row = page.getByRole('row', { name: /Наушники Apple AirPods Pro 2/ })
  const updatedAt = await row.locator('time').getAttribute('datetime')
  expect(Date.now() - Date.parse(updatedAt ?? '')).toBeLessThan(30 * 60_000)
  const expectedDate = await page.evaluate((value) => new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit',
  }).format(new Date(value)), updatedAt ?? '')
  await row.click()
  await expect(page.getByText(`Обновлено: ${expectedDate}`)).toBeVisible()
})

test('предложения показывают текущую и среднюю цену', async ({ page }) => {
  await page.goto('/deals')
  await expect(page.getByRole('heading', { name: 'Выгодные предложения' })).toBeVisible()
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toContainText('72 990 ₽')
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toContainText('78 000 ₽')
  await page.screenshot({ path: '/tmp/price-watch-deals.png' })
})

test('ошибки запуска можно повторить отдельно', async ({ page }) => {
  await page.goto('/runs?run=20')
  const details = page.getByRole('region', { name: 'Подробности запуска 20' })
  await expect(details.getByText(/Повторить только карточки с ошибками/)).toBeVisible()
  await details.getByRole('button', { name: 'Повторить ошибки' }).click()
  await expect(page).toHaveURL(/\/runs\?run=22/)
  await expect(page.getByText('Повтор запуска')).toBeVisible()
})
