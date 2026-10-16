import { expect, test } from '@playwright/test'
import { readFile } from 'node:fs/promises'

test('группа объединяет товары и сохраняет индивидуальные карточки', async ({ page }) => {
  await page.goto('/cards')
  await page.getByRole('button', { name: 'Создать группу' }).click()
  const dialog = page.getByRole('dialog', { name: 'Создать группу' })
  await dialog.getByPlaceholder('Например, бутылка').fill('Бутылка')
  await dialog.getByRole('checkbox').nth(0).check()
  await dialog.getByRole('checkbox').nth(1).check()
  await dialog.getByRole('button', { name: 'Сохранить' }).click()
  const group = page.getByRole('row', { name: /Бутылка/ })
  await expect(group).toContainText('24 990 ₽')
  await expect(group.locator('td').nth(3)).toContainText('24 990 ₽')
  await page.getByRole('checkbox', { name: 'Выгодные предложения' }).click()
  await expect(page.getByRole('checkbox', { name: 'Выгодные предложения' })).toBeChecked()
  await expect(page.getByRole('row', { name: /Бутылка/ })).toBeVisible()
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toBeVisible()
  await expect(page.getByRole('row', { name: /Наушники Apple AirPods Pro 2/ })).toHaveCount(0)
  await page.getByRole('checkbox', { name: 'Выгодные предложения' }).click()
  await expect(page.getByRole('row', { name: /Наушники Apple AirPods Pro 2/ })).toBeVisible()
  await page.screenshot({ path: '/tmp/price-watch-groups-list.png' })
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toBeVisible()
  await group.locator('.product-group__toggle').click()
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toHaveCount(0)
  await group.locator('.product-group__toggle').click()
  await page.getByRole('button', { name: 'Сетка' }).click()
  await expect(page.locator('.cards-grid__group .cards-grid__item')).toHaveCount(2)
  await page.screenshot({ path: '/tmp/price-watch-groups-grid.png' })
  await page.getByRole('button', { name: 'Изменить группу Бутылка' }).click()
  const edit = page.getByRole('dialog', { name: 'Изменить группу' })
  await edit.getByPlaceholder('Например, бутылка').fill('Техника')
  await edit.getByRole('button', { name: 'Сохранить' }).click()
  await expect(page.locator('.cards-grid__group')).toContainText('Техника')
  const downloadPromise = page.waitForEvent('download')
  await page.getByLabel('Дополнительные действия').click()
  await page.getByRole('button', { name: 'Экспорт', exact: true }).click()
  const exported = JSON.parse(await readFile(await (await downloadPromise).path(), 'utf8'))
  expect(exported.groups).toEqual([{ name: 'Техника', cards: [
    { marketplace: 'ozon', externalId: '1604900984' },
    { marketplace: 'ozon', externalId: '1587342210' },
  ] }])
  await page.getByRole('button', { name: 'Изменить группу Техника' }).click()
  await edit.getByRole('button', { name: 'Удалить группу' }).click()
  await edit.getByRole('button', { name: 'Подтвердить удаление' }).click()
  await expect(page.locator('.cards-grid__group')).toHaveCount(0)
  await expect(page.getByRole('link', { name: /Смартфон Samsung Galaxy S24/ })).toBeVisible()
  await page.getByLabel('Дополнительные действия').click()
  await page.getByRole('button', { name: 'Импорт', exact: true }).click()
  const importDialog = page.getByRole('dialog', { name: 'Импорт карточек и истории' })
  await importDialog.locator('input[type="file"]').setInputFiles({
    name: 'price-watch-export.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(exported)),
  })
  await expect(importDialog).toContainText('объединено: 5')
  await importDialog.getByRole('button', { name: 'Импортировать' }).click()
  await expect(page.locator('.cards-grid__group')).toContainText('Техника')
})

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
  const productImage = page.locator('.detail-header__product .product-placeholder')
  await expect(productImage).toBeVisible()
  const imageBox = await productImage.boundingBox()
  const titleBox = await page.getByRole('heading', { name: 'Смартфон Samsung Galaxy S24' }).boundingBox()
  expect(imageBox?.width).toBeGreaterThanOrEqual(150)
  expect(imageBox?.x).toBeLessThan(titleBox?.x ?? 0)
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
  await expect(page.getByRole('link', { name: 'Запуски' })).toHaveCount(0)
  await expect(page.getByLabel('Состояние обновления цен')).toContainText('1 из 1', { timeout: 8_000 })
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

test('фильтры не сдвигаются при сбросе, а сетка занимает доступную ширину', async ({ page }) => {
  await page.setViewportSize({ width: 1536, height: 900 })
  await page.goto('/cards')
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toBeVisible()
  const marketplace = page.getByRole('combobox', { name: 'Маркетплейс' })
  const status = page.getByRole('combobox', { name: 'Состояние' })
  const sort = page.getByRole('combobox', { name: 'Сортировка' })
  const before = await Promise.all([marketplace, status, sort].map((control) => control.boundingBox()))
  await status.selectOption('excluded')
  await expect(page.getByRole('button', { name: 'Сбросить' })).toBeVisible()
  const after = await Promise.all([marketplace, status, sort].map((control) => control.boundingBox()))
  for (let index = 0; index < before.length; index += 1) {
    expect(after[index]?.x).toBeCloseTo(before[index]?.x ?? 0, 0)
    expect(after[index]?.y).toBeCloseTo(before[index]?.y ?? 0, 0)
  }
  const reset = await page.getByRole('button', { name: 'Сбросить' }).boundingBox()
  expect(reset?.y).toBeGreaterThan((after[1]?.y ?? 0) + (after[1]?.height ?? 0))
  await expect(status).toHaveValue('excluded')
  await page.screenshot({ path: '/tmp/price-watch-filters.png' })
  await page.setViewportSize({ width: 1024, height: 768 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: '/tmp/price-watch-filters-compact.png' })
  await page.getByRole('button', { name: 'Сбросить' }).click()
  await page.getByRole('button', { name: 'Сетка' }).click()
  const grid = page.getByRole('list', { name: 'Отслеживаемые карточки маркетплейсов' })
  const width = await grid.evaluate((element) => {
    const tiles = Array.from(element.querySelectorAll(':scope > .cards-grid__item'))
    const right = Math.max(...tiles.map((tile) => tile.getBoundingClientRect().right))
    return { gridRight: element.getBoundingClientRect().right, tileRight: right }
  })
  expect(width.gridRight - width.tileRight).toBeLessThan(2)
  await expect(grid.locator('.cards-grid__item').filter({ hasText: 'Наушники Apple AirPods Pro 2' })).toContainText('Сейчас не выгодно')
  await page.screenshot({ path: '/tmp/price-watch-grid-filled.png' })
})

test('заголовки таблицы переключают единственную сортировку по трём состояниям', async ({ page }) => {
  await page.goto('/cards')
  const rows = page.locator('.cards-table tbody tr')
  await expect(rows).toHaveCount(5)
  await expect(rows.first()).toContainText('Смартфон Samsung Galaxy S24')
  const sort = page.getByRole('combobox', { name: 'Сортировка' })
  await expect(sort).toHaveValue('default')

  const price = page.getByRole('columnheader', { name: 'Цена' })
  await price.getByRole('button').click()
  await expect(price).toHaveAttribute('aria-sort', 'ascending')
  await expect(rows.first()).toContainText('Умные часы Xiaomi Watch S3')
  await expect(page).toHaveURL(/sort=price-asc/)
  await expect(sort).toHaveValue('price-asc')
  await page.screenshot({ path: '/tmp/price-watch-sort-ascending.png' })

  await price.getByRole('button').click()
  await expect(price).toHaveAttribute('aria-sort', 'descending')
  await expect(rows.first()).toContainText('Смартфон Samsung Galaxy S24')
  await expect(page).toHaveURL(/sort=price-desc/)

  await price.getByRole('button').click()
  await expect(price).toHaveAttribute('aria-sort', 'none')
  await expect(rows.first()).toContainText('Смартфон Samsung Galaxy S24')
  await expect(page).not.toHaveURL(/sort=/)
  await expect(sort).toHaveValue('default')

  const title = page.getByRole('columnheader', { name: 'Карточка' })
  await title.getByRole('button').click()
  await expect(title).toHaveAttribute('aria-sort', 'ascending')
  await expect(rows.first()).toContainText('Наушники Apple AirPods Pro 2')
  await expect(sort).toHaveValue('title-asc')
  await price.getByRole('button').click()
  await expect(title).toHaveAttribute('aria-sort', 'none')
  await expect(price).toHaveAttribute('aria-sort', 'ascending')

  for (const label of ['Маркетплейс', 'Минимальная', 'Средняя', 'Выгода', 'Наличие']) {
    const heading = page.getByRole('columnheader', { name: label })
    await heading.getByRole('button').click()
    await expect(heading).toHaveAttribute('aria-sort', 'ascending')
    await expect(price).toHaveAttribute('aria-sort', 'none')
  }
  await sort.selectOption('updated-desc')
  await expect(page).toHaveURL(/sort=updated-desc/)
  await expect(page.getByRole('columnheader', { name: 'Наличие' })).toHaveAttribute('aria-sort', 'none')
  await price.getByRole('button').click()
  await expect(sort).toHaveValue('price-asc')
})

test('карточки переключаются между списком и адаптивной сеткой', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 })
  await page.goto('/cards')
  const row = page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })
  await expect(row).toBeVisible()
  const rowHeight = await row.evaluate((element) => element.getBoundingClientRect().height)
  await page.getByRole('button', { name: 'Сетка' }).click()
  const grid = page.getByRole('list', { name: 'Отслеживаемые карточки маркетплейсов' })
  await expect(grid.locator('li')).toHaveCount(5)
  const compactColumns = await grid.evaluate((element) => getComputedStyle(element).gridTemplateColumns.split(' ').length)
  expect(compactColumns).toBeGreaterThan(1)
  const image = grid.locator('.product-placeholder--large').first()
  const tile = grid.locator('li').first()
  const imageBox = await image.boundingBox()
  const tileBox = await tile.boundingBox()
  expect(imageBox?.width).toBeCloseTo((tileBox?.width ?? 0) - 2, 0)
  expect(imageBox?.height).toBeCloseTo(imageBox?.width ?? 0, 0)
  await page.screenshot({ path: '/tmp/price-watch-grid.png' })
  await grid.locator('li').first().getByRole('button', { name: /Действия с карточкой/ }).click()
  await expect(page.getByRole('menuitem', { name: 'Исключить из выгодных предложений' })).toBeVisible()
  await page.keyboard.press('Escape')
  await page.getByRole('heading', { name: 'Карточки' }).click()
  await page.setViewportSize({ width: 1536, height: 900 })
  const wideColumns = await grid.evaluate((element) => getComputedStyle(element).gridTemplateColumns.split(' ').length)
  expect(wideColumns).toBeGreaterThan(compactColumns)
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

test('вертикальное фото видно целиком, а время обновления стоит перед наличием', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 900 })
  await page.goto('/cards')
  await page.getByLabel('Дополнительные действия').click()
  await page.getByRole('button', { name: 'Импорт', exact: true }).click()
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="400"><rect width="200" height="400" fill="blue"/></svg>'
  const imported = {
    version: 1,
    cards: [{
      marketplace: 'ozon', externalId: 'portrait-test', title: 'Вертикальное фото',
      url: null, imageUrl: `data:image/svg+xml,${encodeURIComponent(svg)}`,
      isActive: true, createdAt: new Date().toISOString(),
      history: [{ price: '100.00', availability: 'in_stock', observedAt: new Date().toISOString() }],
    }],
  }
  const dialog = page.getByRole('dialog', { name: 'Импорт карточек и истории' })
  await dialog.locator('input[type="file"]').setInputFiles({
    name: 'portrait.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(imported)),
  })
  await expect(dialog).toContainText('Добавлено карточек: 1')
  await dialog.getByRole('button', { name: 'Импортировать' }).click()
  await page.getByRole('button', { name: 'Сетка' }).click()

  const tile = page.locator('.cards-grid__item').filter({ hasText: 'Вертикальное фото' })
  const image = tile.locator('img')
  await expect(image).toBeVisible()
  const dimensions = await image.evaluate((element) => ({
    width: element.getBoundingClientRect().width,
    height: element.getBoundingClientRect().height,
    naturalWidth: element.naturalWidth,
    naturalHeight: element.naturalHeight,
  }))
  expect(dimensions.naturalWidth).toBe(200)
  expect(dimensions.naturalHeight).toBe(400)
  expect(dimensions.height).toBeCloseTo(dimensions.width * 2, 0)
  const updatedAt = await tile.locator('time').boundingBox()
  const availability = await tile.locator('.status').boundingBox()
  expect(updatedAt?.x).toBeLessThan(availability?.x ?? 0)
  await page.screenshot({ path: '/tmp/price-watch-grid-portrait.png' })
})

test('экспорт и импорт объединяют карточки и историю', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 })
  await page.goto('/cards')
  const downloadPromise = page.waitForEvent('download')
  await page.getByLabel('Дополнительные действия').click()
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
  await page.getByLabel('Дополнительные действия').click()
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

test('исключённые карточки остаются в конце при любой сортировке и в сетке', async ({ page }) => {
  await page.goto('/cards')
  const row = page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })
  await row.getByRole('button', { name: /Действия с карточкой/ }).click()
  await page.getByRole('menuitem', { name: 'Исключить из выгодных предложений' }).click()

  const rows = page.locator('.cards-table tbody tr')
  for (const column of ['Карточка', 'Цена', 'Минимальная', 'Средняя', 'Выгода', 'Наличие']) {
    await page.getByRole('button', { name: column, exact: true }).click()
    await expect(rows.nth(2)).not.toContainText('Не показывается в выгодных предложениях')
    await expect(rows.nth(3)).toContainText('Не показывается в выгодных предложениях')
    await expect(rows.nth(4)).toContainText('Не показывается в выгодных предложениях')
  }

  await page.getByRole('button', { name: 'Сетка' }).click()
  const tiles = page.locator('.cards-grid__item')
  await expect(tiles.nth(3)).toContainText('Не показывается в выгодных предложениях')
  await expect(tiles.nth(4)).toContainText('Не показывается в выгодных предложениях')
})

test('исключённая карточка обновляется, но не попадает в выгодные предложения', async ({ page }) => {
  await page.goto('/cards?deals=1')
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toBeVisible()

  await page.getByRole('checkbox', { name: 'Выгодные предложения' }).click()
  await expect(page.getByRole('checkbox', { name: 'Выгодные предложения' })).not.toBeChecked()
  const row = page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })
  await row.getByRole('button', { name: /Действия с карточкой/ }).click()
  await page.getByRole('menuitem', { name: 'Исключить из выгодных предложений' }).click()
  await expect(row).toContainText('Не показывается в выгодных предложениях')
  await page.getByLabel('Состояние').selectOption('excluded')
  await expect(row).toBeVisible()

  await page.getByRole('checkbox', { name: 'Выгодные предложения' }).click()
  await expect(page.getByRole('checkbox', { name: 'Выгодные предложения' })).toBeChecked()
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toHaveCount(0)
  await page.getByRole('checkbox', { name: 'Выгодные предложения' }).click()
  await expect(page.getByRole('checkbox', { name: 'Выгодные предложения' })).not.toBeChecked()
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
  await expect(page.getByText('Цены обновлены')).toBeHidden({ timeout: 3_000 })
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

test('ошибки сбора доступны без страницы запусков', async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem('price-watch-active-run', '20'))
  await page.goto('/cards')
  const panel = page.getByLabel('Состояние обновления цен')
  await expect(panel.getByText('Показать ошибки')).toBeVisible()
  await panel.getByText('Показать ошибки').click()
  await expect(panel.getByText('Не удалось получить страницу товара', { exact: true })).toBeVisible()
  await panel.getByText('Технические подробности').click()
  await expect(panel.getByText('MarketplaceUnavailable: Не удалось получить страницу товара')).toBeVisible()
  await page.screenshot({ path: '/tmp/price-watch-collection-error.png' })
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
  await expect(page.getByRole('columnheader', { name: 'Обновлено' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Сетка' }).click()
  const tile = page.locator('.cards-grid__item').filter({ hasText: 'Наушники Apple AirPods Pro 2' })
  const updatedAt = await tile.locator('time').getAttribute('datetime')
  expect(Date.now() - Date.parse(updatedAt ?? '')).toBeLessThan(30 * 60_000)
  const expectedDate = await page.evaluate((value) => new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit',
  }).format(new Date(value)), updatedAt ?? '')
  await tile.getByRole('link').click()
  await expect(page.getByText(`Обновлено: ${expectedDate}`)).toBeVisible()
})

test('фильтр предложений показывает цену, минимум, среднюю и выгоду', async ({ page }) => {
  await page.goto('/cards')
  await expect(page.getByRole('columnheader', { name: 'Минимальная' })).toBeVisible()
  await page.getByRole('checkbox', { name: 'Выгодные предложения' }).click()
  await expect(page.getByRole('checkbox', { name: 'Выгодные предложения' })).toBeChecked()
  await expect(page).toHaveURL(/deals=1/)
  await expect(page.getByRole('row', { name: /Наушники Apple AirPods Pro 2/ })).toHaveCount(0)
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toContainText('72 990 ₽')
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toContainText('78 000 ₽')
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ }).locator('td').nth(3)).toContainText('72 990 ₽')
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ }).locator('td').nth(5)).toContainText('5 010 ₽')
  await page.screenshot({ path: '/tmp/price-watch-deals-filter.png' })
  await page.getByRole('button', { name: 'Сетка' }).click()
  await expect(page.locator('.cards-grid__item')).toHaveCount(1)
  await expect(page.locator('.cards-grid__item')).toContainText(['78 000 ₽'])
  await page.goto('/deals')
  await expect(page).toHaveURL(/\/cards$/)
})

test('ошибки запуска можно повторить отдельно', async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem('price-watch-active-run', '20'))
  await page.goto('/cards')
  const panel = page.getByLabel('Состояние обновления цен')
  await panel.getByRole('button', { name: 'Повторить ошибки' }).click()
  await expect(panel).toContainText('0 из 1')
  await expect(page).toHaveURL(/\/cards$/)
})
