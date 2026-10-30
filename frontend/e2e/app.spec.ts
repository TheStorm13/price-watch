import { expect, test, type Locator } from '@playwright/test'
import { readFile } from 'node:fs/promises'

async function chooseOption(control: Locator, label: string) {
  await control.click()
  await control.page().getByRole('option', { name: label, exact: true }).click()
  await expect(control).toHaveAttribute('aria-expanded', 'false')
}

test('выбор в списке сохраняется при поиске и создаёт группу с найденными карточками', async ({ page }) => {
  await page.goto('/cards')
  const samsung = page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })
  const airpods = page.getByRole('row', { name: /Наушники Apple AirPods Pro 2/ })
  await samsung.getByRole('checkbox', { name: /Выбрать карточку/ }).check()
  await airpods.getByRole('checkbox', { name: /Выбрать карточку/ }).check()
  await expect(page).toHaveURL(/\/cards(?:\?|$)/)
  const bulk = page.getByRole('group', { name: 'Действия с выбранными карточками' })
  await expect(bulk).toContainText('Выбрано карточек: 2')
  for (const width of [1024, 1536]) {
    await page.setViewportSize({ width, height: 900 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    await page.screenshot({ path: `/tmp/price-watch-bulk-list-${width}.png`, fullPage: true })
  }
  await page.getByLabel('Поиск карточек').fill('Dyson')
  await expect(bulk).toContainText('Выбрано карточек: 2')
  await page.getByLabel('Поиск карточек').fill('')
  await chooseOption(page.getByRole('combobox', { name: 'Сортировка' }), 'Сначала дороже')
  await chooseOption(page.getByRole('combobox', { name: 'Состояние' }), 'Нет в наличии')
  await expect(bulk).toContainText('Выбрано карточек: 2')
  await chooseOption(page.getByRole('combobox', { name: 'Состояние' }), 'Все состояния')
  await bulk.getByRole('button', { name: 'Создать группу' }).click()
  const dialog = page.getByRole('dialog', { name: 'Создать группу' })
  await expect(dialog).toContainText('Выбрано карточек: 2')
  await dialog.getByRole('button', { name: 'Отмена' }).click()
  await expect(bulk).toContainText('Выбрано карточек: 2')
  await bulk.getByRole('button', { name: 'Создать группу' }).click()
  await dialog.getByRole('textbox', { name: 'Поиск карточек' }).fill('Dyson')
  await dialog.getByRole('checkbox', { name: /Пылесос Dyson/ }).check()
  await dialog.getByRole('textbox', { name: 'Поиск карточек' }).fill('нет совпадений')
  await expect(dialog).toContainText('Карточки не найдены')
  await expect(dialog).toContainText('Выбрано карточек: 3')
  await dialog.getByRole('textbox', { name: 'Поиск карточек' }).fill('')
  await expect(dialog.locator('.group-dialog__card')).toHaveCount(5)
  const ascending = await dialog.locator('.group-dialog__card strong').allTextContents()
  await chooseOption(dialog.getByRole('combobox', { name: 'Сортировка карточек' }), 'По названию: Я–А')
  const descending = await dialog.locator('.group-dialog__card strong').allTextContents()
  expect(descending).toEqual([...ascending].reverse())
  await dialog.getByRole('textbox', { name: 'Название' }).fill('Выбранные товары')
  await dialog.getByRole('button', { name: 'Сохранить' }).click()
  await expect(page.getByRole('row', { name: /Выбранные товары/ })).toContainText('3 товаров')
  await expect(bulk).toHaveCount(0)
})

test('выбранные карточки добавляются в существующую группу без потери её участников', async ({ page }) => {
  await page.goto('/cards')
  await page.getByRole('button', { name: 'Создать группу' }).click()
  const dialog = page.getByRole('dialog', { name: 'Создать группу' })
  await dialog.getByRole('textbox', { name: 'Название' }).fill('Первая группа')
  await dialog.getByRole('checkbox', { name: /Смартфон Samsung/ }).check()
  await dialog.getByRole('button', { name: 'Сохранить' }).click()
  await page.getByRole('button', { name: 'Создать группу' }).click()
  await dialog.getByRole('textbox', { name: 'Название' }).fill('Вторая группа')
  await dialog.getByRole('checkbox', { name: /Наушники Apple/ }).check()
  await dialog.getByRole('button', { name: 'Сохранить' }).click()
  await page.getByRole('row', { name: /Наушники Apple/ }).getByRole('checkbox').check()
  await page.getByRole('row', { name: /Пылесос Dyson/ }).getByRole('checkbox').check()
  const bulk = page.getByRole('group', { name: 'Действия с выбранными карточками' })
  await page.getByRole('row', { name: /Вторая группа/ }).locator('.product-group__toggle').click()
  await expect(bulk).toContainText('Выбрано карточек: 2')
  await bulk.getByRole('button', { name: 'Добавить в группу' }).click()
  await chooseOption(bulk.getByRole('combobox', { name: 'Существующая группа' }), 'Первая группа')
  await expect(bulk).toContainText('Карточки из других групп перейдут')
  await bulk.getByRole('button', { name: 'Добавить карточки' }).click()
  await expect(page.getByRole('row', { name: /Первая группа/ })).toContainText('3 товаров')
  await expect(page.getByRole('row', { name: /Вторая группа/ })).toContainText('0 товаров')
  await expect(bulk).toHaveCount(0)
})

test('массовые действия меняют участие и удаляют карточки только после подтверждения', async ({ page }) => {
  await page.goto('/cards')
  const historyCount = async () => page.evaluate(async () => {
    const modulePath = '/src/api/mockApi.ts'
    const { mockApi } = await import(/* @vite-ignore */ modulePath)
    const exported = await mockApi.exportCards()
    return exported.cards.find((card: { externalId: string }) => card.externalId === '1604900984')?.history.length ?? null
  })
  const originalHistoryCount = await historyCount()
  const samsung = page.getByRole('row', { name: /Смартфон Samsung/ })
  const airpods = page.getByRole('row', { name: /Наушники Apple/ })
  await samsung.getByRole('checkbox').check()
  await airpods.getByRole('checkbox').check()
  const bulk = page.getByRole('group', { name: 'Действия с выбранными карточками' })
  await bulk.getByRole('button', { name: 'Не учитывать в выгодных' }).click()
  await expect(samsung).toContainText('Не участвует в выгодных')
  await expect(airpods).toContainText('Не участвует в выгодных')
  await samsung.getByRole('checkbox').check()
  await airpods.getByRole('checkbox').check()
  await bulk.getByRole('button', { name: 'Учитывать в выгодных', exact: true }).click()
  await expect(samsung).not.toContainText('Не участвует в выгодных')
  expect(await historyCount()).toBe(originalHistoryCount)
  await samsung.getByRole('checkbox').check()
  await airpods.getByRole('checkbox').check()
  await bulk.getByRole('button', { name: 'Удалить выбранные' }).click()
  const confirm = page.getByRole('alertdialog', { name: 'Удалить выбранные карточки?' })
  await expect(confirm).toContainText('Будет удалено карточек: 2')
  await expect(confirm).toContainText('история цен')
  await confirm.getByRole('button', { name: 'Отмена' }).click()
  await expect(samsung).toBeVisible()
  await expect(bulk).toContainText('Выбрано карточек: 2')
  await bulk.getByRole('button', { name: 'Удалить выбранные' }).click()
  await confirm.getByRole('button', { name: 'Удалить карточки' }).click()
  await expect(samsung).toHaveCount(0)
  await expect(airpods).toHaveCount(0)
  expect(await historyCount()).toBeNull()
  await expect(page.getByRole('status')).toContainText('Удалено карточек: 2')
})

test('при частичном отказе массового удаления неуспешная карточка остаётся выбранной', async ({ page }) => {
  await page.goto('/cards')
  await page.evaluate(async () => {
    const modulePath = '/src/api/mockApi.ts'
    const { mockApi } = await import(/* @vite-ignore */ modulePath)
    const original = mockApi.deleteCard.bind(mockApi)
    mockApi.deleteCard = async (id: number) => {
      if (id === 2) throw new Error('Карточка участвует в незавершённом запуске')
      return original(id)
    }
  })
  await page.getByRole('row', { name: /Смартфон Samsung/ }).getByRole('checkbox').check()
  await page.getByRole('row', { name: /Наушники Apple/ }).getByRole('checkbox').check()
  const bulk = page.getByRole('group', { name: 'Действия с выбранными карточками' })
  await bulk.getByRole('button', { name: 'Удалить выбранные' }).click()
  await page.getByRole('alertdialog', { name: 'Удалить выбранные карточки?' }).getByRole('button', { name: 'Удалить карточки' }).click()
  await expect(page.getByRole('row', { name: /Смартфон Samsung/ })).toHaveCount(0)
  await expect(page.getByRole('row', { name: /Наушники Apple/ }).getByRole('checkbox')).toBeChecked()
  await expect(bulk).toContainText('Выбрано карточек: 1')
  await expect(page.getByRole('alert')).toContainText('Не удалось обработать: Наушники Apple')
})

test('ошибка добавления в группу и частичное изменение участия сохраняют выбор', async ({ page }) => {
  await page.goto('/cards')
  await page.getByRole('button', { name: 'Создать группу' }).click()
  const dialog = page.getByRole('dialog', { name: 'Создать группу' })
  await dialog.getByRole('textbox', { name: 'Название' }).fill('Целевая группа')
  await dialog.getByRole('button', { name: 'Сохранить' }).click()
  await page.getByRole('row', { name: /Смартфон Samsung/ }).getByRole('checkbox').check()
  await page.getByRole('row', { name: /Наушники Apple/ }).getByRole('checkbox').check()
  await page.evaluate(async () => {
    const modulePath = '/src/api/mockApi.ts'
    const { mockApi } = await import(/* @vite-ignore */ modulePath)
    mockApi.updateGroup = async () => { throw new Error('Не удалось сохранить группу') }
    const originalUpdate = mockApi.updateCard.bind(mockApi)
    mockApi.updateCard = async (id: number, input: Parameters<typeof mockApi.updateCard>[1]) => {
      if (id === 2) throw new Error('Не удалось изменить карточку')
      return originalUpdate(id, input)
    }
  })
  const bulk = page.getByRole('group', { name: 'Действия с выбранными карточками' })
  await bulk.getByRole('button', { name: 'Добавить в группу' }).click()
  await chooseOption(bulk.getByRole('combobox', { name: 'Существующая группа' }), 'Целевая группа')
  await bulk.getByRole('button', { name: 'Добавить карточки' }).click()
  await expect(page.getByRole('alert')).toContainText('Не удалось сохранить группу')
  await expect(bulk).toContainText('Выбрано карточек: 2')
  await bulk.getByRole('button', { name: 'Не учитывать в выгодных' }).click()
  await expect(page.getByRole('row', { name: /Смартфон Samsung/ })).toContainText('Не участвует в выгодных')
  await expect(page.getByRole('row', { name: /Наушники Apple/ }).getByRole('checkbox')).toBeChecked()
  await expect(bulk).toContainText('Выбрано карточек: 1')
  await expect(page.getByRole('alert')).toContainText('Не удалось обработать: Наушники Apple')
})

test('группа объединяет товары и сохраняет индивидуальные карточки', async ({ page }) => {
  await page.goto('/cards')
  await page.getByRole('button', { name: 'Создать группу' }).click()
  const dialog = page.getByRole('dialog', { name: 'Создать группу' })
  await dialog.getByPlaceholder('Например, бутылка').fill('Бутылка')
  await dialog.getByRole('checkbox', { name: /Смартфон Samsung Galaxy S24/ }).check()
  await dialog.getByRole('checkbox', { name: /Наушники Apple AirPods Pro 2/ }).check()
  await dialog.getByRole('button', { name: 'Сохранить' }).click()
  const group = page.getByRole('row', { name: /Бутылка/ })
  await expect(group).toContainText('24 990 ₽')
  await expect(group.locator('td').nth(4)).toContainText('24 990 ₽')
  await page.getByRole('checkbox', { name: 'Выгодные предложения' }).click()
  await expect(page.getByRole('checkbox', { name: 'Выгодные предложения' })).toBeChecked()
  // The cheapest member (AirPods) is not a deal; Samsung only gives the group display priority.
  await expect(page.getByRole('row', { name: /Бутылка/ })).toHaveCount(0)
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toHaveCount(0)
  await expect(page.getByRole('row', { name: /Наушники Apple AirPods Pro 2/ })).toHaveCount(0)
  await page.getByRole('checkbox', { name: 'Выгодные предложения' }).click()
  await expect(page.getByRole('row', { name: /Наушники Apple AirPods Pro 2/ })).toBeVisible()
  await page.screenshot({ path: '/tmp/price-watch-groups-list.png' })
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toBeVisible()
  await group.locator('.product-group__toggle').click()
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toHaveCount(0)
  await group.locator('.product-group__toggle').click()
  await page.getByRole('radio', { name: 'Сетка' }).click()
  const grid = page.getByRole('list', { name: 'Отслеживаемые карточки маркетплейсов' })
  await expect(grid.locator('.cards-grid--nested .cards-grid__item')).toHaveCount(2)
  await chooseOption(page.getByRole('combobox', { name: 'Сортировка' }), 'Сначала дороже')
  await expect(grid.locator(':scope > li').first()).toHaveClass(/cards-grid__group/)
  for (const width of [1024, 1536]) {
    await page.setViewportSize({ width, height: 900 })
    const tileWidths = await grid.evaluate((element) => ({
      grouped: element.querySelector('.cards-grid--nested .cards-grid__item')?.getBoundingClientRect().width ?? 0,
      standalone: element.querySelector('.virtual-grid-row:not([data-group-member]) .cards-grid__item')?.getBoundingClientRect().width ?? 0,
    }))
    expect(tileWidths.grouped).toBeGreaterThan(0)
    expect(Math.abs(tileWidths.grouped - tileWidths.standalone)).toBeLessThan(16)
  }
  await page.screenshot({ path: '/tmp/price-watch-groups-grid.png' })
  await page.getByRole('button', { name: 'Изменить группу Бутылка' }).click()
  const edit = page.getByRole('dialog', { name: 'Изменить группу' })
  await edit.getByPlaceholder('Например, бутылка').fill('Техника')
  await edit.getByRole('button', { name: 'Сохранить' }).click()
  await expect(page.locator('.cards-grid__group')).toContainText('Техника')
  const downloadPromise = page.waitForEvent('download')
  await page.getByLabel('Дополнительные действия').click()
  await page.getByRole('menuitem', { name: 'Экспорт', exact: true }).click()
  const exported = JSON.parse(await readFile(await (await downloadPromise).path(), 'utf8'))
  expect(exported.groups).toEqual([{ name: 'Техника', tags: [], cards: [
    { marketplace: 'ozon', externalId: '1604900984' },
    { marketplace: 'ozon', externalId: '1587342210' },
  ] }])
  await page.getByRole('button', { name: 'Изменить группу Техника' }).click()
  await edit.getByRole('button', { name: 'Удалить группу' }).click()
  await page.getByRole('alertdialog', { name: 'Удалить группу?' }).getByRole('button', { name: 'Подтвердить удаление' }).click()
  await expect(page.locator('.cards-grid__group')).toHaveCount(0)
  await expect(page.getByRole('link', { name: /Смартфон Samsung Galaxy S24/ })).toBeVisible()
  await page.getByLabel('Дополнительные действия').click()
  await page.getByRole('menuitem', { name: 'Импорт', exact: true }).click()
  const importDialog = page.getByRole('dialog', { name: 'Импорт карточек и истории' })
  await importDialog.locator('input[type="file"]').setInputFiles({
    name: 'price-watch-export.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(exported)),
  })
  await expect(importDialog).toContainText('объединено: 5')
  await importDialog.getByRole('button', { name: 'Импортировать' }).click()
  await expect(page.locator('.cards-grid__group')).toContainText('Техника')
})

test('товарный фильтр использует теги представителя, теги группы сохраняются отдельно', async ({ page }) => {
  await page.goto('/cards/1')
  await page.getByRole('textbox', { name: 'Теги товара' }).fill('электроника, подарок')
  await page.getByRole('button', { name: 'Сохранить теги' }).click()
  await expect(page.locator('.detail-page > .tag-list')).toContainText('подарок')
  await page.getByRole('link', { name: 'К карточкам' }).click()
  await page.getByRole('row', { name: /Наушники Apple/ }).click()
  await page.getByRole('textbox', { name: 'Теги товара' }).fill('аудио')
  await page.getByRole('button', { name: 'Сохранить теги' }).click()
  await expect(page.locator('.detail-page > .tag-list')).toContainText('аудио')
  await page.getByRole('link', { name: 'К карточкам' }).click()
  await page.getByRole('button', { name: 'Создать группу' }).click()
  const dialog = page.getByRole('dialog', { name: 'Создать группу' })
  await dialog.getByPlaceholder('Например, бутылка').fill('Техника')
  await dialog.getByRole('textbox', { name: 'Теги группы' }).fill('дом')
  await dialog.getByRole('checkbox', { name: /Наушники Apple/ }).check()
  await dialog.getByRole('button', { name: 'Сохранить' }).click()
  await chooseOption(page.getByRole('combobox', { name: 'Тег' }), 'аудио')
  await expect(page.getByRole('row', { name: /Техника/ })).toBeVisible()
  await page.getByRole('button', { name: 'Изменить группу Техника' }).click()
  await expect(page.getByRole('textbox', { name: 'Теги группы' })).toHaveValue('дом')
  await page.getByRole('dialog', { name: 'Изменить группу' }).getByRole('button', { name: 'Отмена' }).click()
  await expect(page.getByRole('row', { name: /Наушники Apple/ })).toBeVisible()
  await expect(page.getByRole('row', { name: /Смартфон Samsung/ })).toHaveCount(0)
  await chooseOption(page.getByRole('combobox', { name: 'Тег' }), 'подарок')
  await expect(page.getByRole('row', { name: /Смартфон Samsung/ })).toBeVisible()
  await expect(page.getByRole('row', { name: /Техника/ })).toHaveCount(0)
})

test('основной сценарий интерфейса в браузерном E2E', async ({ page }) => {
  const errors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text())
  })

  await page.setViewportSize({ width: 1536, height: 1024 })
  await page.goto('/cards')
  await expect(page).toHaveTitle('price-watch')
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
  await expect(page.getByRole('menuitem', { name: 'Не учитывать в выгодных предложениях' })).toBeVisible()
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

test('карточки площадок без коннектора добавляются без запуска сбора', async ({ page }) => {
  await page.goto('/cards')
  for (const [marketplace, title, id] of [
    ['Яндекс Маркет', 'Бутылка Яндекс', '246813579'],
  ]) {
    await page.getByRole('button', { name: 'Добавить карточку' }).click()
    const drawer = page.getByRole('dialog', { name: 'Добавить карточку' })
    await drawer.getByRole('radio', { name: new RegExp(marketplace) }).check()
    await drawer.getByRole('textbox', { name: 'ID карточки' }).fill(id)
    await drawer.getByRole('textbox', { name: 'Название' }).fill(title)
    await drawer.getByRole('button', { name: 'Добавить', exact: true }).click()
    const row = page.getByRole('row', { name: new RegExp(title) })
    await expect(row).toBeVisible()
    await row.getByRole('button', { name: /Действия с карточкой/ }).click()
    await expect(page.getByRole('menuitem', { name: 'Обновить только эту карточку' })).toHaveCount(0)
    await page.keyboard.press('Escape')
    await row.click()
    await expect(page.getByText('Сбор цен пока недоступен: коннектор не подключён')).toBeVisible()
    await page.getByRole('link', { name: 'К карточкам' }).click()
  }
  await chooseOption(page.getByRole('combobox', { name: 'Маркетплейс' }), 'Яндекс Маркет')
  await expect(page.getByRole('row', { name: /Бутылка Яндекс/ })).toBeVisible()
  await expect(page.getByRole('row', { name: /Бутылка WB/ })).toHaveCount(0)
  await chooseOption(page.getByRole('combobox', { name: 'Маркетплейс' }), 'Все маркетплейсы')
  await page.getByRole('button', { name: 'Обновить цены' }).click()
  await expect(page.getByLabel('Состояние обновления цен')).toContainText('из 5')
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
  await chooseOption(status, 'Не участвует в выгодных')
  await expect(page.getByRole('button', { name: 'Сбросить' })).toBeVisible()
  const after = await Promise.all([marketplace, status, sort].map((control) => control.boundingBox()))
  for (let index = 0; index < before.length; index += 1) {
    expect(after[index]?.x).toBeCloseTo(before[index]?.x ?? 0, 0)
    expect(after[index]?.y).toBeCloseTo(before[index]?.y ?? 0, 0)
  }
  const reset = await page.getByRole('button', { name: 'Сбросить' }).boundingBox()
  expect(reset?.y).toBeGreaterThanOrEqual(after[1]?.y ?? 0)
  await expect(status).toHaveText('Не участвует в выгодных')
  await page.screenshot({ path: '/tmp/price-watch-filters.png' })
  await page.setViewportSize({ width: 1024, height: 768 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: '/tmp/price-watch-filters-compact.png' })
  await page.getByRole('button', { name: 'Сбросить' }).click()
  await page.getByRole('radio', { name: 'Сетка' }).click()
  await expect(page).toHaveURL(/\/cards\?view=grid$/)
  await expect(status).toHaveText('Все состояния')
  await expect(page.getByRole('button', { name: 'Сбросить' })).toHaveCount(0)
  const grid = page.getByRole('list', { name: 'Отслеживаемые карточки маркетплейсов' })
  await expect(grid.locator('.virtual-grid-row:not([data-group-member]) .cards-grid__item')).toHaveCount(5)
  const width = await grid.evaluate((element) => {
    const tiles = Array.from(element.querySelectorAll('.virtual-grid-row:not([data-group-member]) .cards-grid__item'))
    const right = Math.max(...tiles.map((tile) => tile.getBoundingClientRect().right))
    return { gridRight: element.getBoundingClientRect().right, tileRight: right }
  })
  expect(width.gridRight - width.tileRight).toBeLessThan(2)
  await expect(grid.locator('.cards-grid__item').filter({ hasText: 'Наушники Apple AirPods Pro 2' })).toContainText('Сейчас не выгодно')
  await page.screenshot({ path: '/tmp/price-watch-grid-filled.png' })
  await chooseOption(status, 'Не участвует в выгодных')
  await expect(grid.locator('.virtual-grid-row:not([data-group-member]) .cards-grid__item')).toHaveCount(1)
  await page.getByRole('button', { name: 'Сбросить' }).click()
  await expect(page.getByRole('radio', { name: 'Сетка' })).toBeChecked()
  await expect(page).toHaveURL(/\/cards\?view=grid$/)
  await expect(status).toHaveText('Все состояния')
  await expect(grid.locator('.virtual-grid-row:not([data-group-member]) .cards-grid__item')).toHaveCount(5)
})

test('заголовки таблицы переключают единственную сортировку по трём состояниям', async ({ page }) => {
  await page.goto('/cards')
  const rows = page.locator('.cards-table tbody tr')
  await expect(rows).toHaveCount(5)
  await expect(rows.first()).toContainText('Смартфон Samsung Galaxy S24')
  const sort = page.getByRole('combobox', { name: 'Сортировка' })
  await expect(sort).toHaveText('По умолчанию')

  const price = page.getByRole('columnheader', { name: 'Цена' })
  await price.getByRole('button').click()
  await expect(price).toHaveAttribute('aria-sort', 'ascending')
  await expect(rows.first()).toContainText('Смартфон Samsung Galaxy S24')
  await expect(rows.nth(1)).toContainText('Умные часы Xiaomi Watch S3')
  await expect(page).toHaveURL(/sort=price-asc/)
  await expect(sort).toHaveText('Сначала дешевле')
  await page.screenshot({ path: '/tmp/price-watch-sort-ascending.png' })

  await price.getByRole('button').click()
  await expect(price).toHaveAttribute('aria-sort', 'descending')
  await expect(rows.first()).toContainText('Смартфон Samsung Galaxy S24')
  await expect(page).toHaveURL(/sort=price-desc/)

  await price.getByRole('button').click()
  await expect(price).toHaveAttribute('aria-sort', 'none')
  await expect(rows.first()).toContainText('Смартфон Samsung Galaxy S24')
  await expect(page).not.toHaveURL(/sort=/)
  await expect(sort).toHaveText('По умолчанию')

  const title = page.getByRole('columnheader', { name: 'Карточка' })
  await title.getByRole('button').click()
  await expect(title).toHaveAttribute('aria-sort', 'ascending')
  await expect(rows.first()).toContainText('Смартфон Samsung Galaxy S24')
  await expect(rows.nth(1)).toContainText('Конструктор LEGO Technic McLaren P1')
  await expect(sort).toHaveText('Карточка ↑')
  await price.getByRole('button').click()
  await expect(title).toHaveAttribute('aria-sort', 'none')
  await expect(price).toHaveAttribute('aria-sort', 'ascending')

  for (const label of ['Маркетплейс', 'Минимальная', 'Средняя', 'Выгода', 'Наличие']) {
    const heading = page.getByRole('columnheader', { name: label })
    await heading.getByRole('button').click()
    await expect(heading).toHaveAttribute('aria-sort', 'ascending')
    await expect(price).toHaveAttribute('aria-sort', 'none')
  }
  await chooseOption(sort, 'Недавно обновлённые')
  await expect(page).toHaveURL(/sort=updated-desc/)
  await expect(page.getByRole('columnheader', { name: 'Наличие' })).toHaveAttribute('aria-sort', 'none')
  await price.getByRole('button').click()
  await expect(sort).toHaveText('Сначала дешевле')
})

test('карточки переключаются между списком и адаптивной сеткой', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 })
  await page.goto('/cards')
  const row = page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })
  await expect(row).toBeVisible()
  const rowHeight = await row.evaluate((element) => element.getBoundingClientRect().height)
  await page.getByRole('radio', { name: 'Сетка' }).click()
  const grid = page.getByRole('list', { name: 'Отслеживаемые карточки маркетплейсов' })
  await expect(grid.locator('.cards-grid__item')).toHaveCount(5)
  const compactColumns = await grid.evaluate((element) => getComputedStyle(element.querySelector('.cards-grid')!).gridTemplateColumns.split(' ').length)
  expect(compactColumns).toBeGreaterThan(1)
  const image = grid.locator('.product-placeholder--large').first()
  const tile = grid.locator('.cards-grid__item').first()
  const imageBox = await image.boundingBox()
  const tileBox = await tile.boundingBox()
  expect(imageBox?.width).toBeCloseTo((tileBox?.width ?? 0) - 2, 0)
  expect(imageBox?.height).toBe(190)
  await page.screenshot({ path: '/tmp/price-watch-grid.png' })
  await grid.locator('.cards-grid__item').first().getByRole('button', { name: /Действия с карточкой/ }).click()
  await expect(page.getByRole('menuitem', { name: 'Не учитывать в выгодных предложениях' })).toBeVisible()
  await page.keyboard.press('Escape')
  await page.getByRole('heading', { name: 'Карточки' }).click()
  await page.setViewportSize({ width: 1536, height: 900 })
  const wideColumns = await grid.evaluate((element) => getComputedStyle(element.querySelector('.cards-grid')!).gridTemplateColumns.split(' ').length)
  expect(wideColumns).toBeGreaterThan(compactColumns)
  await page.screenshot({ path: '/tmp/price-watch-grid-wide.png' })
  await page.reload()
  await expect(grid.locator('.cards-grid__item')).toHaveCount(5)
  await grid.getByRole('link', { name: /Смартфон Samsung Galaxy S24/ }).click()
  await expect(page).toHaveURL(/\/cards\/1/)
  await page.setViewportSize({ width: 1024, height: 768 })
  await page.goto('/cards?view=grid')
  await page.getByRole('radio', { name: 'Список' }).click()
  await expect(row).toBeVisible()
  expect(await row.evaluate((element) => element.getBoundingClientRect().height)).toBe(rowHeight)
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
})

test('плитки одинаковы при разных фото, а метаданные списка помещаются в строку', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 900 })
  await page.goto('/cards')
  await page.getByLabel('Дополнительные действия').click()
  await page.getByRole('menuitem', { name: 'Импорт', exact: true }).click()
  const portrait = '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="400"><rect width="200" height="400" fill="blue"/></svg>'
  const landscape = '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200"><rect width="400" height="200" fill="green"/></svg>'
  const imported = {
    version: 2,
    cards: [
      {
        marketplace: 'ozon', externalId: 'portrait-test',
        title: 'Очень длинное название вертикального товара, которое должно обрезаться внутри двух строк плитки',
        url: null, imageUrl: `data:image/svg+xml,${encodeURIComponent(portrait)}`,
        tags: ['длинный тег для проверки фиксированной области', 'ещё один тег'],
        dealsEnabled: false, createdAt: new Date().toISOString(),
        history: [{ price: '100.00', availability: 'in_stock', observedAt: new Date().toISOString() }],
      },
      {
        marketplace: 'ozon', externalId: 'landscape-test', title: 'Горизонтальное фото',
        url: null, imageUrl: `data:image/svg+xml,${encodeURIComponent(landscape)}`,
        dealsEnabled: true, createdAt: new Date().toISOString(), history: [],
      },
    ],
  }
  const dialog = page.getByRole('dialog', { name: 'Импорт карточек и истории' })
  await dialog.locator('input[type="file"]').setInputFiles({
    name: 'portrait.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(imported)),
  })
  await expect(dialog).toContainText('Добавлено карточек: 2')
  await dialog.getByRole('button', { name: 'Импортировать' }).click()
  const excludedRow = page.getByRole('row', { name: /Очень длинное название вертикального товара/ })
  const ordinaryRow = page.getByRole('row', { name: /Горизонтальное фото/ })
  for (const width of [1024, 1536]) {
    await page.setViewportSize({ width, height: 900 })
    const badge = excludedRow.locator('.tracking-status')
    const rowBoxes = await Promise.all([excludedRow.boundingBox(), ordinaryRow.boundingBox(), badge.boundingBox()])
    expect(rowBoxes[0]!.height).toBeGreaterThanOrEqual(rowBoxes[1]!.height)
    expect(rowBoxes[2]!.y).toBeGreaterThanOrEqual(rowBoxes[0]!.y)
    expect(rowBoxes[2]!.y + rowBoxes[2]!.height).toBeLessThanOrEqual(rowBoxes[0]!.y + rowBoxes[0]!.height)
    const firstCell = await excludedRow.locator('td').nth(1).boundingBox()
    const titleBox = (await excludedRow.locator('.card-identity strong').boundingBox())!
    expect(titleBox.x + titleBox.width).toBeLessThanOrEqual(firstCell!.x + firstCell!.width)
    expect((rowBoxes[2]?.x ?? 0) + (rowBoxes[2]?.width ?? 0)).toBeLessThanOrEqual((firstCell?.x ?? 0) + (firstCell?.width ?? 0))
  }
  await excludedRow.scrollIntoViewIfNeeded()
  await page.screenshot({ path: '/tmp/price-watch-list-uniform.png', fullPage: true })

  await page.getByRole('radio', { name: 'Сетка' }).click()
  const grid = page.getByRole('list', { name: 'Отслеживаемые карточки маркетплейсов' })
  const portraitTile = grid.locator('.cards-grid__item').filter({ hasText: 'Очень длинное название вертикального товара' })
  const landscapeTile = grid.locator('.cards-grid__item').filter({ hasText: 'Горизонтальное фото' })
  await expect(grid.locator('.cards-grid__item')).toHaveCount(7)
  for (const width of [1024, 1536]) {
    await page.setViewportSize({ width, height: 900 })
    const tiles = await grid.locator('.cards-grid__item').all()
    const tileBoxes = await Promise.all(tiles.map((tile) => tile.boundingBox()))
    const widths = tileBoxes.map((box) => box?.width ?? 0)
    const heights = tileBoxes.map((box) => box?.height ?? 0)
    expect(Math.max(...widths) - Math.min(...widths)).toBeLessThan(1)
    expect(Math.max(...heights) - Math.min(...heights)).toBeLessThan(1)
    const imageBoxes = await Promise.all([portraitTile, landscapeTile].map((tile) => tile.locator('.product-placeholder--large').boundingBox()))
    for (const tile of [portraitTile, landscapeTile]) {
      const [tileBox, mediaBox] = await Promise.all([tile.boundingBox(), tile.locator('.cards-grid__media').boundingBox()])
      expect(mediaBox!.y - tileBox!.y).toBeGreaterThanOrEqual(8)
    }
    expect(imageBoxes[0]?.height).toBe(190)
    expect(imageBoxes[1]?.height).toBe(190)
    const positions = await Promise.all([portraitTile, landscapeTile, grid.locator('.cards-grid__item').first()].map((tile) => tile.evaluate((element) => {
      const top = element.getBoundingClientRect().top
      return ['.cards-grid__media', '.cards-grid__title', '.cards-grid__tags', '.cards-grid__prices', 'time']
        .map((selector) => element.querySelector(selector)!.getBoundingClientRect().top - top)
    })))
    for (let index = 0; index < positions[0].length; index += 1) {
      const offsets = positions.map((card) => card[index])
      expect(Math.max(...offsets) - Math.min(...offsets)).toBeLessThan(1)
    }
    const badgeBox = await portraitTile.locator('.tracking-status').boundingBox()
    expect(badgeBox?.height).toBeGreaterThanOrEqual(18)
  }
  for (const [tile, naturalWidth, naturalHeight] of [[portraitTile, 200, 400], [landscapeTile, 400, 200]] as const) {
    const image = tile.locator('img')
    await expect(image).toBeVisible()
    const dimensions = await image.evaluate((element) => ({
      naturalWidth: element.naturalWidth,
      naturalHeight: element.naturalHeight,
      fit: getComputedStyle(element).objectFit,
    }))
    expect(dimensions).toEqual({ naturalWidth, naturalHeight, fit: 'contain' })
  }
  expect(await portraitTile.locator('.cards-grid__title').getAttribute('title')).toContain('Очень длинное название')
  const updatedAt = await portraitTile.locator('time').boundingBox()
  const availability = await portraitTile.getByText('В наличии', { exact: true }).boundingBox()
  expect(updatedAt?.x).toBeLessThan(availability?.x ?? 0)

  const layout = () => portraitTile.evaluate((element) => {
    const tile = element.getBoundingClientRect()
    const section = (selector: string) => {
      const rect = element.querySelector(selector)!.getBoundingClientRect()
      return { top: rect.top - tile.top, height: rect.height }
    }
    return {
      height: tile.height,
      image: section('.product-placeholder--large'),
      title: section('.cards-grid__title'),
      prices: section('.cards-grid__prices'),
      time: section('time'),
    }
  })
  for (const width of [1536, 1024]) {
    await page.setViewportSize({ width, height: 900 })
    const beforeToggle = await layout()
    await portraitTile.getByRole('button', { name: /Действия с карточкой/ }).click()
    await page.getByRole('menuitem', { name: 'Учитывать в выгодных предложениях' }).click()
    await expect(portraitTile.locator('.tracking-status')).toHaveCount(0)
    await expect(page.getByRole('menu')).toBeHidden()
    expect(await layout()).toEqual(beforeToggle)
    await portraitTile.getByRole('button', { name: /Действия с карточкой/ }).click()
    await page.getByRole('menuitem', { name: 'Не учитывать в выгодных предложениях' }).click()
    await expect(portraitTile.locator('.tracking-status')).toHaveText('Не участвует в выгодных')
    await expect(page.getByRole('menu')).toBeHidden()
    expect(await layout()).toEqual(beforeToggle)
  }
  await page.screenshot({ path: '/tmp/price-watch-grid-uniform.png', fullPage: true })
})

test('экспорт и импорт объединяют карточки и историю', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 })
  await page.goto('/cards')
  const downloadPromise = page.waitForEvent('download')
  await page.getByLabel('Дополнительные действия').click()
  await page.getByRole('menuitem', { name: 'Экспорт', exact: true }).click()
  const download = await downloadPromise
  const exportData = JSON.parse(await readFile(await download.path(), 'utf8'))
  expect(exportData.cards).toHaveLength(5)
  expect(exportData.cards[0].history[0]).toEqual(expect.objectContaining({
    price: expect.any(String), availability: expect.any(String), observedAt: expect.any(String),
  }))
  expect(exportData.version).toBe(2)
  expect(exportData.cards[0]).not.toHaveProperty('isActive')
  expect(exportData.cards[0]).not.toHaveProperty('isArchived')
  exportData.cards.push({
    marketplace: 'ozon', externalId: '9999911111', title: 'Тестовый импорт',
    url: null, dealsEnabled: false, createdAt: new Date().toISOString(),
    history: [{ price: '123.00', availability: 'in_stock', observedAt: new Date().toISOString() }],
  })
  await page.getByLabel('Дополнительные действия').click()
  await page.getByRole('menuitem', { name: 'Импорт', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Импорт карточек и истории' })
  await dialog.locator('input[type="file"]').setInputFiles({
    name: 'price-watch-export.json', mimeType: 'application/json',
    buffer: Buffer.from(JSON.stringify(exportData)),
  })
  await expect(dialog).toContainText('Добавлено карточек: 1, объединено: 5')
  await page.screenshot({ path: '/tmp/price-watch-import-preview.png' })
  await dialog.getByRole('button', { name: 'Импортировать' }).click()
  await expect(page.getByRole('row', { name: /Тестовый импорт/ })).toBeVisible()
  await expect(page.getByRole('row', { name: /Тестовый импорт/ })).toContainText('Не участвует в выгодных')
  await page.screenshot({ path: '/tmp/price-watch-imported.png' })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
})

test('меню карточки управляет показом в выгодных предложениях', async ({ page }) => {
  await page.goto('/cards')
  const row = page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })
  await row.getByRole('button', { name: /Действия с карточкой/ }).click()
  await expect(page.getByRole('menuitem', { name: 'Не учитывать в выгодных предложениях' })).toBeVisible()
  await expect(page.getByRole('menuitem', { name: 'В архив' })).toHaveCount(0)
  await page.getByRole('menuitem', { name: 'Не учитывать в выгодных предложениях' }).click()
  await expect(row.getByText('Не участвует в выгодных')).toBeVisible()

  await row.getByRole('button', { name: /Действия с карточкой/ }).click()
  await expect(page.getByRole('menuitem', { name: 'Учитывать в выгодных предложениях' })).toBeVisible()
  await page.screenshot({ path: '/tmp/price-watch-card-actions.png' })
  await page.getByRole('menuitem', { name: 'Учитывать в выгодных предложениях' }).click()
  await expect(row.getByText('Не участвует в выгодных')).toBeHidden()
})

test('исключённые карточки идут последними по умолчанию и используют общий ключ при ручной сортировке', async ({ page }) => {
  await page.goto('/cards')
  const row = page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })
  await row.getByRole('button', { name: /Действия с карточкой/ }).click()
  await page.getByRole('menuitem', { name: 'Не учитывать в выгодных предложениях' }).click()
  const rows = page.locator('.cards-table tbody tr')
  await expect(rows.nth(3)).toContainText('Не участвует в выгодных')
  await expect(rows.nth(4)).toContainText('Не участвует в выгодных')
  await chooseOption(page.getByRole('combobox', { name: 'Сортировка' }), 'Сначала дешевле')
  await expect(rows.nth(0)).toContainText('Умные часы Xiaomi Watch S3')
  await expect(rows.nth(2)).toContainText('Конструктор LEGO Technic McLaren P1')
  await expect(rows.nth(3)).toContainText('Смартфон Samsung Galaxy S24')
  await expect(rows.nth(4)).toContainText('Пылесос Dyson V12 Detect Slim')
  await page.getByRole('radio', { name: 'Сетка' }).click()
  const tiles = page.locator('.cards-grid__item')
  await expect(tiles.nth(0)).toContainText('Умные часы Xiaomi Watch S3')
  await expect(tiles.nth(2)).toContainText('Конструктор LEGO Technic McLaren P1')
  await expect(tiles.nth(3)).toContainText('Смартфон Samsung Galaxy S24')
  await expect(tiles.nth(4)).toContainText('Пылесос Dyson V12 Detect Slim')
})

test('исключённая карточка обновляется, но не попадает в выгодные предложения', async ({ page }) => {
  await page.goto('/cards?deals=1')
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toBeVisible()

  await page.getByRole('checkbox', { name: 'Выгодные предложения' }).click()
  await expect(page.getByRole('checkbox', { name: 'Выгодные предложения' })).not.toBeChecked()
  const row = page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })
  await row.getByRole('button', { name: /Действия с карточкой/ }).click()
  await page.getByRole('menuitem', { name: 'Не учитывать в выгодных предложениях' }).click()
  await expect(row).toContainText('Не участвует в выгодных')
  await chooseOption(page.getByLabel('Состояние'), 'Не участвует в выгодных')
  await expect(row).toBeVisible()

  await page.getByRole('checkbox', { name: 'Выгодные предложения' }).click()
  await expect(page.getByRole('checkbox', { name: 'Выгодные предложения' })).toBeChecked()
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toHaveCount(0)
  await page.getByRole('checkbox', { name: 'Выгодные предложения' }).click()
  await expect(page.getByRole('checkbox', { name: 'Выгодные предложения' })).not.toBeChecked()
  await chooseOption(page.getByLabel('Состояние'), 'Не участвует в выгодных')
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
  await row.getByRole('button', { name: /Действия с карточкой/ }).click()
  await page.getByRole('menuitem', { name: 'Удалить карточку' }).click()
  await dialog.getByRole('button', { name: 'Удалить', exact: true }).click()
  await expect(row).toBeHidden()
})

test('запуск доходит до проверки и продолжается', async ({ page }) => {
  await page.goto('/cards')
  await page.getByRole('button', { name: 'Обновить цены' }).click()
  await expect(page.getByLabel('Состояние обновления цен')).toBeVisible()
  await expect(page.getByLabel('Состояние обновления цен')).toContainText('0 из 5')
  await expect(page.getByText('Требуется проверка в Chrome')).toBeVisible({ timeout: 8_000 })
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
  await page.addInitScript(() => window.localStorage.setItem('price-watch-active-run', '21'))
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
  await page.getByRole('radio', { name: 'Сетка' }).click()
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
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toContainText('77 878,89 ₽')
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ }).locator('td').nth(4)).toContainText('72 990 ₽')
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ }).locator('td').nth(6)).toContainText('4 888,89 ₽')
  await page.screenshot({ path: '/tmp/price-watch-deals-filter.png' })
  await page.getByRole('radio', { name: 'Сетка' }).click()
  await expect(page.locator('.cards-grid__item')).toHaveCount(1)
  await expect(page.locator('.cards-grid__item')).toContainText(['77 878,89 ₽'])
  await page.goto('/deals')
  await expect(page).toHaveURL(/\/cards$/)
})

test('после повторного открытия видны сохранённые предложения и результат запуска', async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem('price-watch-active-run', '21'))
  await page.goto('/cards?deals=1')
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toContainText('72 990 ₽')
  await expect(page.getByLabel('Состояние обновления цен')).toContainText('Показать ошибки')

  await page.reload()
  await expect(page.getByRole('checkbox', { name: 'Выгодные предложения' })).toBeChecked()
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toContainText('4 888,89 ₽')
  const run = page.getByLabel('Состояние обновления цен')
  await run.getByText('Показать ошибки').click()
  await expect(run).toContainText('Не удалось получить страницу товара')
})

test('ошибки запуска можно повторить отдельно', async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem('price-watch-active-run', '20'))
  await page.goto('/cards')
  const panel = page.getByLabel('Состояние обновления цен')
  await panel.getByRole('button', { name: 'Повторить ошибки' }).click()
  await expect(panel).toContainText('0 из 1')
  await expect(page).toHaveURL(/\/cards$/)
})

test('старые подробности очищены, но число ошибок и повтор сохранены', async ({page})=>{
  await page.addInitScript(()=>window.localStorage.setItem('price-watch-active-run','20'))
  await page.goto('/cards')
  const panel=page.getByLabel('Состояние обновления цен')
  await expect(panel).toContainText('Ошибок: 1')
  await expect(panel).toContainText('Подробности очищены')
  await expect(panel.getByText('Показать ошибки')).toHaveCount(0)
  await expect(panel.getByRole('button',{name:'Повторить ошибки и оставшиеся'})).toBeVisible()
})

test('панель и диалог удерживают фокус и возвращают его после Escape', async ({ page }) => {
  await page.goto('/cards')
  const add = page.getByRole('button', { name: 'Добавить карточку', exact: true })
  await add.click()
  const sheet = page.getByRole('dialog', { name: 'Добавить карточку' })
  await expect(sheet.getByRole('textbox', { name: 'ID карточки' })).toBeFocused()
  for (const key of ['Shift+Tab', 'Tab']) {
    for (let step = 0; step < 12; step += 1) {
      await page.keyboard.press(key)
      expect(await sheet.evaluate((element) => element.contains(document.activeElement))).toBe(true)
    }
  }
  await page.keyboard.press('Escape')
  await expect(sheet).toHaveCount(0)
  await expect(add).toBeFocused()

  const create = page.getByRole('button', { name: 'Создать группу', exact: true })
  await create.click()
  const dialog = page.getByRole('dialog', { name: 'Создать группу' })
  await expect(dialog.getByRole('textbox', { name: 'Название', exact: true })).toBeFocused()
  for (const key of ['Tab', 'Shift+Tab']) {
    for (let step = 0; step < 14; step += 1) {
      await page.keyboard.press(key)
      expect(await dialog.evaluate((element) => element.contains(document.activeElement))).toBe(true)
    }
  }
  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)
  await expect(create).toBeFocused()
})

test('переход меню → подтверждение → отмена возвращает фокус без удаления', async ({ page }) => {
  await page.goto('/cards')
  await page.evaluate(async () => {
    const { mockApi } = await import('/src/api/mockApi.ts')
    mockApi.deleteCard = async () => { throw new Error('Отмена не должна вызывать удаление') }
  })
  const row = page.getByRole('row', { name: /Смартфон Samsung/ })
  const trigger = row.getByRole('button', { name: /Действия с карточкой/ })
  await trigger.click()
  await page.getByRole('menuitem', { name: 'Удалить карточку', exact: true }).click()
  const confirm = page.getByRole('alertdialog', { name: 'Удалить карточку?' })
  await expect(confirm.getByRole('button', { name: 'Отмена' })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(confirm).toHaveCount(0)
  await expect(trigger).toBeFocused()
  await expect(row).toBeVisible()
  await expect(page.getByRole('alert')).toHaveCount(0)
})

test('выпадающие фильтры оформлены в общей теме и управляются клавиатурой', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/cards')
  await expect(page.getByRole('row', { name: /Смартфон Samsung/ })).toBeVisible()
  for (const width of [1440, 1024]) {
    await page.setViewportSize({ width, height: 900 })
    for (const name of ['Состояние', 'Маркетплейс', 'Сортировка', 'Тег']) {
      const trigger = page.getByRole('combobox', { name, exact: true })
      await trigger.click()
      const popup = page.getByRole('listbox')
      await expect(popup).toBeVisible()
      await expect(popup).toHaveCSS('background-color', 'rgb(255, 255, 255)')
      await expect(popup).toHaveCSS('border-radius', '8px')
      await popup.evaluate(async (element) => {
        await Promise.all(element.getAnimations().map((animation) => animation.finished))
      })
      const bounds = await popup.boundingBox()
      expect(bounds!.x).toBeGreaterThanOrEqual(0)
      expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width)
      if (name === 'Состояние') await page.screenshot({ path: `/tmp/price-watch-select-state-${width}.png` })
      await page.keyboard.press('Escape')
      await expect(popup).toBeHidden()
      await expect(trigger).toBeFocused()
    }
  }
  const state = page.getByRole('combobox', { name: 'Состояние', exact: true })
  await state.press('ArrowDown')
  await expect(page.getByRole('listbox')).toBeVisible()
  await page.keyboard.press('End')
  await expect(page.getByRole('option', { name: 'Не участвует в выгодных', exact: true })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(state).toHaveText('Не участвует в выгодных')
  await expect(state).toBeFocused()
  await expect(page).toHaveURL(/status=deals_disabled/)
  await page.getByRole('button', { name: 'Сбросить' }).click()
  await expect(state).toHaveText('Все состояния')
  expect(errors).toEqual([])
})
