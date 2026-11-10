import { selectMany } from './catalog-controls'
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
  await expect(bulk).toContainText('Выбрано: 2')
  for (const width of [1024, 1536]) {
    await page.setViewportSize({ width, height: 900 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
  }
  await page.getByLabel('Поиск по названию или артикулу').fill('Dyson')
  await expect(bulk).toContainText('Выбрано: 2')
  await page.getByLabel('Поиск по названию или артикулу').fill('')
  await chooseOption(page.getByRole('combobox', { name: 'Сортировка' }), 'Сначала дорогие')
  await page.getByRole('checkbox', { name: 'Только в наличии' }).check()
  await expect(bulk).toContainText('Выбрано: 2')
  await page.getByRole('checkbox', { name: 'Только в наличии' }).uncheck()
  await bulk.getByRole('button', { name: 'Создать группу' }).click()
  const dialog = page.getByRole('dialog', { name: 'Создать группу' })
  await expect(dialog).toContainText('Выбрано: 2')
  await dialog.getByRole('button', { name: 'Отмена' }).click()
  await expect(bulk).toContainText('Выбрано: 2')
  await bulk.getByRole('button', { name: 'Создать группу' }).click()
  await dialog.getByRole('textbox', { name: 'Поиск карточек' }).fill('Dyson')
  await dialog.getByRole('checkbox', { name: /Пылесос Dyson/ }).check()
  await dialog.getByRole('textbox', { name: 'Поиск карточек' }).fill('нет совпадений')
  await expect(dialog).toContainText('Карточки не найдены')
  await expect(dialog).toContainText('Выбрано: 3')
  await dialog.getByRole('textbox', { name: 'Поиск карточек' }).fill('')
  await expect(dialog.locator('.group-dialog__card')).toHaveCount(5)
  const ascending = await dialog.locator('.group-dialog__card strong').allTextContents()
  await chooseOption(dialog.getByRole('combobox', { name: 'Сортировка карточек' }), 'По названию: Я–А')
  const descending = await dialog.locator('.group-dialog__card strong').allTextContents()
  expect(descending).toEqual([...ascending].reverse())
  await dialog.getByRole('textbox', { name: 'Название' }).fill('Выбранные товары')
  await dialog.getByRole('button', { name: 'Сохранить' }).click()
  await expect(page.getByRole('row', { name: /Выбранные товары/ })).toContainText('3 из 3 товаров')
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
  await expect(bulk).toContainText('Выбрано: 2')
  await bulk.getByRole('button', { name: 'Добавить в группу' }).click()
  await chooseOption(bulk.getByRole('combobox', { name: 'Существующая группа' }), 'Первая группа')
  await expect(bulk).toContainText('Карточки из других групп перейдут')
  await bulk.getByRole('button', { name: 'Добавить карточки' }).click()
  await expect(page.getByRole('row', { name: /Первая группа/ })).toContainText('3 из 3 товаров')
  await expect(page.getByRole('row', { name: /Вторая группа/ })).toHaveCount(0)
  await expect(bulk).toHaveCount(0)
})

test('массовые действия меняют участие и удаляют карточки только после подтверждения', async ({ page }) => {
  await page.goto('/cards')
  const historyCount = async () => page.evaluate(async () => {
    const modulePath = '/src/api/mockApi.ts'
    const { mockApi } = await import(/* @vite-ignore */ modulePath)
    const exported = await mockApi.exportCards()
    return exported.cards.find((card: { externalId: string }) => card.externalId === '1604900984')?.variants[0].history.length ?? null
  })
  const originalHistoryCount = await historyCount()
  const samsung = page.getByRole('row', { name: /Смартфон Samsung/ })
  const airpods = page.getByRole('row', { name: /Наушники Apple/ })
  await samsung.getByRole('checkbox').check()
  await airpods.getByRole('checkbox').check()
  const bulk = page.getByRole('group', { name: 'Действия с выбранными карточками' })
  await bulk.getByRole('button', { name: 'Исключить из выгодных' }).click()
  await expect(samsung).toContainText('Исключён из выгодных')
  await expect(airpods).toContainText('Исключён из выгодных')
  await samsung.getByRole('checkbox').check()
  await airpods.getByRole('checkbox').check()
  await bulk.getByRole('button', { name: 'Учитывать в выгодных', exact: true }).click()
  await expect(samsung).not.toContainText('Исключён из выгодных')
  expect(await historyCount()).toBe(originalHistoryCount)
  await samsung.getByRole('checkbox').check()
  await airpods.getByRole('checkbox').check()
  await bulk.getByRole('button', { name: 'Удалить выбранные' }).click()
  const confirm = page.getByRole('alertdialog', { name: 'Удалить выбранные карточки?' })
  await expect(confirm).toContainText('Будет удалено карточек: 2')
  await expect(confirm).toContainText('история цен')
  await confirm.getByRole('button', { name: 'Отмена' }).click()
  await expect(samsung).toBeVisible()
  await expect(bulk).toContainText('Выбрано: 2')
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
  await expect(bulk).toContainText('Выбрано: 1')
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
  await expect(bulk).toContainText('Выбрано: 2')
  await bulk.getByRole('button', { name: 'Исключить из выгодных' }).click()
  await expect(page.getByRole('row', { name: /Смартфон Samsung/ })).toContainText('Исключён из выгодных')
  await expect(page.getByRole('row', { name: /Наушники Apple/ }).getByRole('checkbox')).toBeChecked()
  await expect(bulk).toContainText('Выбрано: 1')
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
  await expect(group).toContainText('72 990 ₽')
  await expect(group.locator('td').nth(4)).toContainText('72 990 ₽')
  await chooseOption(page.getByRole('combobox', { name: 'Участие в выгодных' }), 'Выгодные')
  await expect(page.getByRole('combobox', { name: 'Участие в выгодных' })).toHaveText('Выгодные')
  // The eligible Samsung member remains visible; AirPods is excluded by this filter.
  await expect(page.getByRole('row', { name: /Бутылка/ })).toBeVisible()
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toBeVisible()
  await expect(page.getByRole('row', { name: /Наушники Apple AirPods Pro 2/ })).toHaveCount(0)
  await chooseOption(page.getByRole('combobox', { name: 'Участие в выгодных' }), 'Все товары')
  await expect(page.getByRole('row', { name: /Наушники Apple AirPods Pro 2/ })).toBeVisible()
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toBeVisible()
  await group.locator('.product-group__toggle').click()
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toHaveCount(0)
  await group.locator('.product-group__toggle').click()
  await page.getByRole('radio', { name: 'Сетка' }).click()
  const grid = page.getByRole('list', { name: 'Отслеживаемые карточки маркетплейсов' })
  await expect(grid.locator('.cards-grid--nested .cards-grid__item')).toHaveCount(2)
  await chooseOption(page.getByRole('combobox', { name: 'Сортировка' }), 'Сначала дорогие')
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
  await page.getByRole('button', { name: 'Изменить группу Бутылка' }).click()
  const edit = page.getByRole('dialog', { name: 'Изменить группу' })
  await edit.getByPlaceholder('Например, бутылка').fill('Техника')
  await edit.getByRole('button', { name: 'Сохранить' }).click()
  await expect(page.locator('.cards-grid__group')).toContainText('Техника')
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Настройки', exact: true }).click()
  await page.getByRole('dialog', { name: 'Настройки', exact: true }).getByRole('button', { name: 'Экспорт', exact: true }).click()
  const exported = JSON.parse(await readFile(await (await downloadPromise).path(), 'utf8'))
  await page.keyboard.press('Escape')
  expect(exported.groups).toEqual([{ name: 'Техника', tags: [], cards: [
    { marketplace: 'ozon', externalId: '1604900984' },
    { marketplace: 'ozon', externalId: '1587342210' },
  ] }])
  await page.getByRole('button', { name: 'Изменить группу Техника' }).click()
  await edit.getByRole('button', { name: 'Удалить группу' }).click()
  await page.getByRole('alertdialog', { name: 'Удалить группу?' }).getByRole('button', { name: 'Подтвердить удаление' }).click()
  await expect(page.locator('.cards-grid__group')).toHaveCount(0)
  await expect(page.getByRole('link', { name: /Смартфон Samsung Galaxy S24/ })).toBeVisible()
  await page.getByRole('button', { name: 'Настройки', exact: true }).click()
  await page.getByRole('dialog', { name: 'Настройки', exact: true }).getByRole('button', { name: 'Импорт', exact: true }).click()
  const importDialog = page.getByRole('dialog', { name: 'Импорт товаров' })
  await importDialog.locator('input[type="file"]').setInputFiles({
    name: 'price-watch-export.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(exported)),
  })
  await expect(importDialog).toContainText('Объединено: 5')
  await importDialog.getByRole('button', { name: 'Импортировать' }).click()
  await expect(page.locator('.cards-grid__group')).toContainText('Техника')
})

test('товарный фильтр использует теги представителя, теги группы сохраняются отдельно', async ({ page }) => {
  await page.goto('/cards/1')
  await page.getByRole('button', { name: 'Изменить', exact:true }).click()
  await page.getByRole('textbox', { name: 'Теги (до двух, через запятую)', exact:true }).fill('электроника, подарок')
  await page.getByRole('button', { name: 'Сохранить', exact:true }).click()
  await expect(page.locator('.detail-page > .tag-list')).toContainText('подарок')
  await page.getByRole('link', { name: 'К товарам' }).click()
  await page.getByRole('row', { name: /Наушники Apple/ }).click()
  await page.getByRole('button', { name: 'Изменить', exact:true }).click()
  await page.getByRole('textbox', { name: 'Теги (до двух, через запятую)', exact:true }).fill('аудио')
  await page.getByRole('button', { name: 'Сохранить', exact:true }).click()
  await expect(page.locator('.detail-page > .tag-list')).toContainText('аудио')
  await page.getByRole('link', { name: 'К товарам' }).click()
  await page.getByRole('button', { name: 'Создать группу' }).click()
  const dialog = page.getByRole('dialog', { name: 'Создать группу' })
  await dialog.getByPlaceholder('Например, бутылка').fill('Техника')
  await dialog.getByRole('textbox', { name: 'Теги группы (через запятую)' }).fill('дом')
  await dialog.getByRole('checkbox', { name: /Наушники Apple/ }).check()
  await dialog.getByRole('button', { name: 'Сохранить' }).click()
  await selectMany(page, 'Теги', ['аудио'])
  await expect(page.getByRole('row', { name: /Техника/ })).toBeVisible()
  await page.getByRole('button', { name: 'Изменить группу Техника' }).click()
  await expect(page.getByRole('textbox', { name: 'Теги группы (через запятую)' })).toHaveValue('дом')
  await page.getByRole('dialog', { name: 'Изменить группу' }).getByRole('button', { name: 'Отмена' }).click()
  await expect(page.getByRole('row', { name: /Наушники Apple/ })).toBeVisible()
  await expect(page.getByRole('row', { name: /Смартфон Samsung/ })).toHaveCount(0)
  await selectMany(page, 'Теги', ['подарок'])
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
  await expect(page).toHaveTitle('Price watch')
  await expect(page.locator('vite-error-overlay')).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Товары' })).toBeVisible()
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toBeVisible()

  await page.getByRole('button', { name: 'Добавить товар' }).click()
  await expect(page.getByRole('dialog', { name: 'Добавить товар' })).toBeVisible()
  await page.waitForTimeout(250)
  await page.getByRole('button', { name: 'Закрыть', exact: true }).click()

  await page.getByLabel('Поиск по названию или артикулу').fill('Dyson')
  await expect(page.getByRole('row', { name: /Пылесос Dyson/ })).toBeVisible()
  await page.getByLabel('Поиск по названию или артикулу').fill('')
  await page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ }).click()
  await expect(page).toHaveURL(/\/cards\/1/)
  const productImage = page.locator('.detail-header__image .product-placeholder')
  await expect(productImage).toBeVisible()
  const imageBox = await productImage.boundingBox()
  const titleBox = await page.getByRole('heading', { name: 'Смартфон Samsung Galaxy S24' }).boundingBox()
  expect(imageBox?.width).toBeGreaterThanOrEqual(150)
  expect(imageBox?.x).toBeGreaterThan(titleBox?.x ?? 0)
  await expect(page.getByRole('heading', { name: 'История цен' })).toBeVisible()
  await expect(page.getByText('72 990 ₽').first()).toBeVisible()
  await expect(page.getByRole('link', { name: 'Открыть на Ozon' })).toHaveAttribute('href', 'https://www.ozon.ru/product/1604900984')
  await page.getByRole('button', { name: /Действия с карточкой/ }).click()
  await expect(page.getByRole('menuitem', { name: 'Исключить из выгодных' })).toBeVisible()
  await expect(page.getByRole('menuitem', { name: 'Удалить карточку' })).toBeVisible()
  await page.keyboard.press('Escape')
  expect(errors).toEqual([])
})

test('из каталога запускается сбор только выбранной карточки', async ({ page }) => {
  await page.goto('/cards')
  const row = page.getByRole('row', { name: /Наушники Apple AirPods Pro 2/ })
  await row.getByRole('button', { name: /Действия с карточкой/ }).click()
  await page.getByRole('menuitem', { name: 'Обновить цены' }).click()
  await expect(page.getByLabel('Состояние обновления цен')).toContainText('0 из 1')
  await expect(page.getByRole('link', { name: 'Запуски' })).toHaveCount(0)
  await expect(page.getByLabel('Состояние обновления цен')).toContainText('1 из 1', { timeout: 8_000 })
})

test('добавленный товар Маркета поддерживает обновление цен', async ({ page }) => {
  await page.goto('/cards')
  for (const [marketplace, title, id] of [
    ['Яндекс Маркет', 'Бутылка Яндекс', '246813579'],
  ]) {
    await page.getByRole('button', { name: 'Добавить товар' }).click()
    const drawer = page.getByRole('dialog', { name: 'Добавить товар' })
    await drawer.getByRole('radio', { name: new RegExp(marketplace) }).check()
    await drawer.getByRole('textbox', { name: 'Артикул' }).fill(id)
    await drawer.getByRole('textbox', { name: 'Название (необязательно)' }).fill(title)
    await drawer.getByRole('button', { name: 'Добавить', exact: true }).click()
    const row = page.getByRole('row', { name: new RegExp(title) })
    await expect(row).toBeVisible()
    await row.getByRole('button', { name: /Действия с карточкой/ }).click()
    await expect(page.getByRole('menuitem', { name: 'Обновить цены' })).toBeVisible()
    await page.keyboard.press('Escape')
    await row.click()
    await expect(page.getByRole('button', { name: 'Обновить цены', exact: true })).toBeEnabled()
    await page.getByRole('link', { name: 'К товарам' }).click()
  }
  await selectMany(page, 'Маркетплейсы', ['Яндекс Маркет'])
  await expect(page.getByRole('row', { name: /Бутылка Яндекс/ })).toBeVisible()
  await expect(page.getByRole('row', { name: /Бутылка WB/ })).toHaveCount(0)
  await selectMany(page, 'Маркетплейсы', null)
  const running = page.getByLabel('Состояние обновления цен')
  if (await running.isVisible()) {
    await running.getByRole('button', { name: 'Проверка пройдена' }).click()
    await expect(running).toContainText('Цены обновлены', { timeout: 10000 })
    await running.getByRole('button', { name: 'Закрыть', exact: true }).click()
  }
  await page.getByRole('button', { name: 'Обновить все цены' }).click()
  await expect(running).toContainText('из 6')
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

test('фильтры панели сохраняют положение при сбросе, а вид остаётся выбранным', async ({ page }) => {
  for (const width of [1536, 1024]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/cards')
    const sidebar = page.getByRole('complementary', { name: 'Боковая панель', exact: true })
    const controls = [sidebar.getByRole('button', { name: 'Маркетплейсы', exact: true }), sidebar.getByRole('combobox', { name: 'Сортировка' })]
    await expect(controls[0]).toBeVisible()
    const before = await Promise.all(controls.map(control => control.boundingBox()))
    await page.getByRole('checkbox', { name: 'Только в наличии' }).check()
    await page.getByRole('button', { name: 'Сбросить', exact: true }).click()
    await expect(page.getByRole('checkbox', { name: 'Только в наличии' })).not.toBeChecked()
    const after = await Promise.all(controls.map(control => control.boundingBox()))
    expect(after).toEqual(before)
    await page.getByRole('radio', { name: 'Сетка', exact: true }).click()
    await page.getByRole('checkbox', { name: 'Только в наличии' }).check()
    await page.getByRole('button', { name: 'Сбросить', exact: true }).click()
    await expect(page).toHaveURL(/\/cards\?view=grid$/)
    await expect(page.getByRole('radio', { name: 'Сетка' })).toBeChecked()
    await expect(page.locator('.cards-grid__item')).toHaveCount(5)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  }
})

test('сортировка из панели пересекает приоритет выгодности и синхронизирует заголовок', async ({ page }) => {
  await page.goto('/cards')
  const rows = page.locator('.cards-table tbody tr')
  await expect(rows).toHaveCount(5)
  await expect(rows.first()).toContainText('Смартфон Samsung Galaxy S24')
  await expect(page.getByRole('columnheader').getByRole('button').filter({ hasNot: page.locator('svg.lucide-circle-help') })).toHaveCount(7)
  const sort = page.getByRole('combobox', { name: 'Сортировка' })
  await expect(sort).toHaveText('Сначала выгодные')
  await chooseOption(sort, 'Сначала дешёвые')
  await expect(rows.first()).toContainText('Умные часы Xiaomi Watch S3')
  await expect(page).toHaveURL(/sort=price-asc/)
  await expect(page.getByRole('columnheader', { name: 'Цена', exact: true })).toHaveAttribute('aria-sort', 'ascending')
  await chooseOption(sort, 'Сначала дорогие')
  await expect(rows.first()).toContainText('Смартфон Samsung Galaxy S24')
  await chooseOption(sort, 'Сначала выгодные')
  await expect(page).not.toHaveURL(/sort=/)
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
  expect(imageBox!.width / imageBox!.height).toBeCloseTo(3 / 4, 2)
  expect(imageBox!.width).toBeLessThan(tileBox!.width)
  expect(imageBox?.height).toBe(368)
  await grid.locator('.cards-grid__item').first().getByRole('button', { name: /Действия с карточкой/ }).click()
  await expect(page.getByRole('menuitem', { name: 'Исключить из выгодных' })).toBeVisible()
  await page.keyboard.press('Escape')
  await page.getByRole('heading', { name: 'Товары' }).click()
  await page.setViewportSize({ width: 1536, height: 900 })
  const wideColumns = await grid.evaluate((element) => getComputedStyle(element.querySelector('.cards-grid')!).gridTemplateColumns.split(' ').length)
  expect(wideColumns).toBeGreaterThan(compactColumns)
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
  await page.getByRole('button', { name: 'Настройки', exact: true }).click()
  await page.getByRole('dialog', { name: 'Настройки', exact: true }).getByRole('button', { name: 'Импорт', exact: true }).click()
  const portrait = '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="400"><rect width="200" height="400" fill="blue"/></svg>'
  const landscape = '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200"><rect width="400" height="200" fill="green"/></svg>'
  const imported = {
    version: 3,
    cards: [
      {
        marketplace: 'ozon', externalId: '900000001',
        title: 'Очень длинное название вертикального товара, которое должно обрезаться внутри двух строк плитки',
        url: null, imageUrl: `data:image/svg+xml,${encodeURIComponent(portrait)}`,
        tags: ['длинный тег для проверки фиксированной области', 'ещё один тег'],
        dealsEnabled: false, createdAt: new Date().toISOString(),
        history: [{ price: '100.00', availability: 'in_stock', observedAt: new Date().toISOString() }],
      },
      {
        marketplace: 'ozon', externalId: '900000002', title: 'Горизонтальное фото',
        url: null, imageUrl: `data:image/svg+xml,${encodeURIComponent(landscape)}`,
        dealsEnabled: true, createdAt: new Date().toISOString(), history: [],
      },
    ],
  }
  const transfer = {...imported, cards: imported.cards.map(({history,...card}) => ({...card,primaryExternalId:card.externalId,variants:[{externalId:card.externalId,url:card.url,history}]}))}
  const dialog = page.getByRole('dialog', { name: 'Импорт товаров' })
  await dialog.locator('input[type="file"]').setInputFiles({
    name: 'portrait.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(transfer)),
  })
  await expect(dialog).toContainText('Добавлено: 2')
  await dialog.getByRole('button', { name: 'Импортировать' }).click()
  // Keep the photo/layout check independent of the default reordering after a toggle.
  await chooseOption(page.getByRole('combobox', { name: 'Сортировка' }), 'Сначала дешёвые')
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

  await page.getByRole('radio', { name: 'Сетка' }).click()
  const grid = page.getByRole('list', { name: 'Отслеживаемые карточки маркетплейсов' })
  const portraitTile = grid.locator('.cards-grid__item').filter({ hasText: 'Очень длинное название вертикального товара' })
  const landscapeTile = grid.locator('.cards-grid__item').filter({ hasText: 'Горизонтальное фото' })
  async function waitForGridLayout() {
    const columns = await grid.evaluate(element => Math.max(1, Math.floor((element.clientWidth + 8) / 288)))
    await expect(grid.locator('.cards-grid')).toHaveCount(Math.ceil(7 / columns))
    await expect.poll(() => grid.locator('.cards-grid').first().evaluate(element =>
      getComputedStyle(element).gridTemplateColumns.split(' ').length)).toBe(columns)
    await expect(grid.locator('.cards-grid__item')).toHaveCount(7)
    await expect(portraitTile).toBeVisible()
  }
  for (const width of [1024, 1536]) {
    await page.setViewportSize({ width, height: 900 })
    await waitForGridLayout()
    const tileBoxes = await grid.locator('.cards-grid__item').evaluateAll(tiles => tiles.map(tile => {
      const {width,height} = tile.getBoundingClientRect()
      return {width,height}
    }))
    const widths = tileBoxes.map((box) => box?.width ?? 0)
    const heights = tileBoxes.map((box) => box?.height ?? 0)
    expect(Math.max(...widths) - Math.min(...widths)).toBeLessThan(1)
    expect(Math.max(...heights) - Math.min(...heights)).toBeLessThan(1)
    const imageBoxes = await Promise.all([portraitTile, landscapeTile].map((tile) => tile.locator('.product-placeholder--large').boundingBox()))
    for (const tile of [portraitTile, landscapeTile]) {
      const [tileBox, mediaBox] = await Promise.all([tile.boundingBox(), tile.locator('.cards-grid__media').boundingBox()])
      expect(mediaBox!.y - tileBox!.y).toBeGreaterThanOrEqual(8)
    }
    expect(imageBoxes[0]?.height).toBe(368)
    expect(imageBoxes[1]?.height).toBe(368)
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
  for (const tile of [portraitTile, landscapeTile]) {
    const image = tile.locator('img')
    await expect(image).toBeVisible()
    const dimensions = await image.evaluate((element) => ({
      naturalWidth: element.naturalWidth,
      naturalHeight: element.naturalHeight,
      fit: getComputedStyle(element).objectFit,
    }))
    expect(dimensions).toEqual({ naturalWidth: 276, naturalHeight: 368, fit: 'contain' })
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
    await waitForGridLayout()
    const beforeToggle = await layout()
    await portraitTile.getByRole('button', { name: /Действия с карточкой/ }).click()
    await page.getByRole('menuitem', { name: 'Учитывать в выгодных' }).click()
    await expect(portraitTile).not.toContainText('Исключён из выгодных')
    await expect(page.getByRole('menu')).toHaveCount(0)
    expect(await layout()).toEqual(beforeToggle)
    await portraitTile.getByRole('button', { name: /Действия с карточкой/ }).click()
    await page.getByRole('menuitem', { name: 'Исключить из выгодных' }).click()
    await expect(portraitTile.locator('.tracking-status')).toHaveText('Исключён из выгодных')
    await expect(page.getByRole('menu')).toHaveCount(0)
    expect(await layout()).toEqual(beforeToggle)
  }
})

test('экспорт и импорт объединяют карточки и историю', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 })
  await page.goto('/cards')
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Настройки', exact: true }).click()
  await page.getByRole('dialog', { name: 'Настройки', exact: true }).getByRole('button', { name: 'Экспорт', exact: true }).click()
  const download = await downloadPromise
  const exportData = JSON.parse(await readFile(await download.path(), 'utf8'))
  expect(exportData.cards).toHaveLength(5)
  expect(exportData.cards[0].variants[0].history[0]).toEqual(expect.objectContaining({
    price: expect.any(String), availability: expect.any(String), observedAt: expect.any(String),
  }))
  expect(exportData.version).toBe(3)
  expect(exportData.cards[0]).not.toHaveProperty('isActive')
  expect(exportData.cards[0]).not.toHaveProperty('isArchived')
  exportData.cards.push({
    marketplace: 'ozon', externalId: '9999911111', title: 'Тестовый импорт',
    url: null, dealsEnabled: false, createdAt: new Date().toISOString(),
    primaryExternalId:'9999911111',variants:[{externalId:'9999911111',url:null,history: [{ price: '123.00', availability: 'in_stock', observedAt: new Date().toISOString() }]}],
  })
  await page.getByRole('button', { name: 'Настройки', exact: true }).click()
  await page.getByRole('dialog', { name: 'Настройки', exact: true }).getByRole('button', { name: 'Импорт', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Импорт товаров' })
  await dialog.locator('input[type="file"]').setInputFiles({
    name: 'price-watch-export.json', mimeType: 'application/json',
    buffer: Buffer.from(JSON.stringify(exportData)),
  })
  await expect(dialog).toContainText('Добавлено: 1 · Объединено: 5')
  await dialog.getByRole('button', { name: 'Импортировать' }).click()
  await expect(page.getByRole('row', { name: /Тестовый импорт/ })).toBeVisible()
  await expect(page.getByRole('row', { name: /Тестовый импорт/ })).toContainText('Исключён из выгодных')
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
})

test('меню карточки управляет показом в выгодных предложениях', async ({ page }) => {
  await page.goto('/cards')
  const row = page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })
  await row.getByRole('button', { name: /Действия с карточкой/ }).click()
  await expect(page.getByRole('menuitem', { name: 'Исключить из выгодных' })).toBeVisible()
  await expect(page.getByRole('menuitem', { name: 'В архив' })).toHaveCount(0)
  await page.getByRole('menuitem', { name: 'Исключить из выгодных' }).click()
  await expect(row.getByText('Исключён из выгодных')).toBeVisible()

  await row.getByRole('button', { name: /Действия с карточкой/ }).click()
  await expect(page.getByRole('menuitem', { name: 'Учитывать в выгодных' })).toBeVisible()
  await page.getByRole('menuitem', { name: 'Учитывать в выгодных' }).click()
  await expect(row.getByText('Исключён из выгодных')).toBeHidden()
})

test('исключённые карточки идут последними по умолчанию и при ручной сортировке с приоритетом участия', async ({ page }) => {
  await page.goto('/cards')
  const row = page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })
  await row.getByRole('button', { name: /Действия с карточкой/ }).click()
  await page.getByRole('menuitem', { name: 'Исключить из выгодных' }).click()
  const rows = page.locator('.cards-table tbody tr')
  await expect(rows.nth(3)).toContainText('Исключён из выгодных')
  await expect(rows.nth(4)).toContainText('Исключён из выгодных')
  await chooseOption(page.getByRole('combobox', { name: 'Сортировка' }), 'Сначала дешёвые')
  await expect(rows.nth(0)).toContainText('Умные часы Xiaomi Watch S3')
  await expect(rows.nth(2)).toContainText('Пылесос Dyson V12 Detect Slim')
  await expect(rows.nth(3)).toContainText('Конструктор LEGO Technic McLaren P1')
  await expect(rows.nth(4)).toContainText('Смартфон Samsung Galaxy S24')
  await page.getByRole('radio', { name: 'Сетка' }).click()
  const tiles = page.locator('.cards-grid__item')
  await expect(tiles.nth(0)).toContainText('Умные часы Xiaomi Watch S3')
  await expect(tiles.nth(2)).toContainText('Пылесос Dyson V12 Detect Slim')
  await expect(tiles.nth(3)).toContainText('Конструктор LEGO Technic McLaren P1')
  await expect(tiles.nth(4)).toContainText('Смартфон Samsung Galaxy S24')
})

test('исключённая карточка обновляется, но не попадает в выгодные предложения', async ({ page }) => {
  await page.goto('/cards?deals=deals')
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toBeVisible()

  await chooseOption(page.getByRole('combobox', { name: 'Участие в выгодных' }), 'Все товары')
  await expect(page.getByRole('combobox', { name: 'Участие в выгодных' })).toHaveText('Все товары')
  const row = page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })
  await row.getByRole('button', { name: /Действия с карточкой/ }).click()
  await page.getByRole('menuitem', { name: 'Исключить из выгодных' }).click()
  await expect(row).toContainText('Исключён из выгодных')
  await expect(row).toBeVisible()

  await chooseOption(page.getByRole('combobox', { name: 'Участие в выгодных' }), 'Выгодные')
  await expect(page.getByRole('combobox', { name: 'Участие в выгодных' })).toHaveText('Выгодные')
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toHaveCount(0)
  await chooseOption(page.getByRole('combobox', { name: 'Участие в выгодных' }), 'Все товары')
  await expect(page.getByRole('combobox', { name: 'Участие в выгодных' })).toHaveText('Все товары')
  await row.getByRole('button', { name: /Действия с карточкой/ }).click()
  await page.getByRole('menuitem', { name: 'Обновить цены' }).click()
  await expect(page.getByLabel('Состояние обновления цен')).toContainText('0 из 1')
  await page.goto('/cards/1')
  await expect(page.getByRole('button', { name: 'Обновить цены' })).toBeEnabled()
})

test('удаление карточки требует подтверждения', async ({ page }) => {
  await page.goto('/cards')
  const row = page.getByRole('row', { name: /Пылесос Dyson/ })

  await row.getByRole('button', { name: /Действия с карточкой/ }).click()
  await page.getByRole('menuitem', { name: 'Удалить карточку' }).click()
  const dialog = page.getByRole('alertdialog', { name: 'Удалить карточку?' })
  await expect(dialog).toContainText('вся история её цен будут удалены')
  await dialog.getByRole('button', { name: 'Отмена' }).click()
  await expect(row).toBeVisible()
  await row.getByRole('button', { name: /Действия с карточкой/ }).click()
  await page.getByRole('menuitem', { name: 'Удалить карточку' }).click()
  await dialog.getByRole('button', { name: 'Удалить', exact: true }).click()
  await expect(row).toBeHidden()
})

test('запуск доходит до проверки и продолжается', async ({ page }) => {
  await page.goto('/cards')
  await page.getByRole('button', { name: 'Обновить все цены' }).click()
  await expect(page.getByLabel('Состояние обновления цен')).toBeVisible()
  await expect(page.getByLabel('Состояние обновления цен')).toContainText('0 из 5')
  await expect(page.getByText('Требуется проверка в Chrome')).toBeVisible({ timeout: 8_000 })
  await page.getByRole('button', { name: 'Проверка пройдена' }).click()
  await expect(page.getByText('Цены обновлены')).toBeVisible({ timeout: 8_000 })
  await expect(page.getByText('Найдено выгодных предложений:', { exact: false })).toHaveCount(0)
  await expect(page.getByText('Цены обновлены')).toBeHidden({ timeout: 3_000 })
})

test('детали карточки показывают середину диапазона и страницы истории', async ({ page }) => {
  await page.goto('/cards/1')
  await expect(page.getByText('Середина диапазона')).toBeVisible()
  await expect(page.getByText('77 240 ₽', { exact: true })).toBeVisible()
  await expect(page.getByText('Разница', { exact: true })).toBeVisible()
  await expect(page.getByText('8 500 ₽', { exact: true })).toBeVisible()
  await expect(page.getByLabel('График цен вариантов товара')).toBeVisible()
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
})

test('одиночное измерение остаётся точкой на графике с масштабом вокруг цены', async ({ page }) => {
  await page.goto('/cards/2')
  const chart = page.getByLabel('График цен вариантов товара')
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
  await chooseOption(page.getByRole('combobox', { name: 'Участие в выгодных' }), 'Выгодные')
  await expect(page.getByRole('combobox', { name: 'Участие в выгодных' })).toHaveText('Выгодные')
  await expect(page).toHaveURL(/deals=deals/)
  await expect(page.getByRole('row', { name: /Наушники Apple AirPods Pro 2/ })).toHaveCount(0)
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toContainText('72 990 ₽')
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toContainText('77 240 ₽')
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ }).locator('td').nth(4)).toContainText('72 990 ₽')
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ }).locator('td').nth(2)).toContainText('4 250 ₽')
  await page.getByRole('radio', { name: 'Сетка' }).click()
  await expect(page.locator('.cards-grid__item')).toHaveCount(1)
  await expect(page.locator('.cards-grid__item')).toContainText(['77 240 ₽'])
  await page.goto('/deals')
  await expect(page).toHaveURL(/\/cards\?deals=deals&view=grid$/)
  await expect(page.getByRole('combobox', { name: 'Участие в выгодных' })).toHaveText('Выгодные')
  await expect(page.getByRole('radio', { name: 'Сетка' })).toBeChecked()
})

test('после повторного открытия видны сохранённые предложения и результат запуска', async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem('price-watch-active-run', '21'))
  await page.goto('/cards?deals=deals')
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toContainText('72 990 ₽')
  await expect(page.getByLabel('Состояние обновления цен')).toContainText('Показать ошибки')

  await page.reload()
  await expect(page.getByRole('combobox', { name: 'Участие в выгодных' })).toHaveText('Выгодные')
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toContainText('4 250 ₽')
  const run = page.getByLabel('Состояние обновления цен')
  await run.getByText('Показать ошибки').click()
  await expect(run).toContainText('Не удалось получить страницу товара')
})

test('ошибки запуска можно повторить отдельно', async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem('price-watch-active-run', '20'))
  await page.goto('/cards')
  const panel = page.getByLabel('Состояние обновления цен')
  await panel.getByRole('button', { name: 'Повторить неудавшиеся и оставшиеся' }).click()
  await expect(panel).toContainText('0 из 1')
  await expect(page).toHaveURL(/\/cards$/)
})

test('старые подробности очищены, но число ошибок и повтор сохранены', async ({page})=>{
  await page.addInitScript(()=>window.localStorage.setItem('price-watch-active-run','20'))
  await page.goto('/cards')
  const panel=page.getByLabel('Состояние обновления цен')
  await expect(panel).toContainText('Ошибок: 1')
  await expect(panel).toContainText('Подробности прошлого запуска удалены')
  await expect(panel.getByText('Показать ошибки')).toHaveCount(0)
  await expect(panel.getByRole('button',{name:'Повторить неудавшиеся и оставшиеся'})).toBeVisible()
})

test('панель и диалог удерживают фокус и возвращают его после Escape', async ({ page }) => {
  await page.goto('/cards')
  const add = page.getByRole('button', { name: 'Добавить товар', exact: true })
  await add.click()
  const sheet = page.getByRole('dialog', { name: 'Добавить товар' })
  await expect(sheet.getByRole('textbox', { name: 'Артикул' })).toBeFocused()
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
    for (const name of ['Сортировка', 'Участие в выгодных']) {
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
      await page.keyboard.press('Escape')
      await expect(popup).toBeHidden()
      await expect(trigger).toBeFocused()
    }
  }
  const sort = page.getByRole('combobox', { name: 'Сортировка', exact: true })
  await sort.press('ArrowDown')
  await expect(page.getByRole('listbox')).toBeVisible()
  await page.keyboard.press('End')
  await expect(page.getByRole('option', { name: 'Сначала дорогие', exact: true })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(sort).toHaveText('Сначала дорогие')
  await expect(sort).toBeFocused()
  await expect(page).toHaveURL(/sort=price-desc/)
  await page.getByRole('button', { name: 'Сбросить' }).click()
  await expect(sort).toHaveText('Сначала выгодные')
  expect(errors).toEqual([])
})

test('WB и AliExpress добавляются по артикулу без поля SKU', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/cards')
  for (const [marketplace, field, article, title, url] of [
    ['Wildberries', 'Артикул WB', '179224846', 'Все размеры WB', 'https://www.wildberries.ru/catalog/179224846/detail.aspx'],
    ['AliExpress', 'ID товара', '1005009868651525', 'Все SKU Ali', 'https://aliexpress.ru/item/1005009868651525.html'],
  ]) {
    await page.getByRole('button', { name: 'Добавить товар' }).click()
    const drawer = page.getByRole('dialog', { name: 'Добавить товар' })
    await drawer.getByRole('radio', { name: new RegExp(marketplace) }).check()
    await expect(drawer.getByLabel('SKU варианта')).toHaveCount(0)
    await expect(drawer.getByLabel('Код размера WB')).toHaveCount(0)
    await drawer.getByRole('textbox', { name: field, exact: true }).fill(article)
    await expect(drawer.getByRole('button', { name: 'Добавить', exact: true })).toBeEnabled()
    await expect(drawer.getByRole('button', { name: 'Ссылка', exact: true })).toBeDisabled()
    await drawer.getByRole('textbox', { name: 'Название (необязательно)', exact: true }).fill(title)
    await drawer.getByRole('button', { name: 'Добавить', exact: true }).click()
    await expect(drawer).toBeHidden()
    await expect(page.getByRole('row', { name: new RegExp(title) })).toBeVisible()
  }
  expect(errors).toEqual([])
})

test('три режима выгодности сохраняются после перезагрузки и сочетаются с поиском', async ({ page }) => {
  await page.goto('/cards')
  const filter = page.getByRole('combobox', { name: 'Участие в выгодных' })
  const rows = page.locator('.cards-table__product')
  await expect(filter).toHaveText('Все товары')
  await expect(rows).toHaveCount(5)
  const total = await rows.count()
  await chooseOption(filter, 'Выгодные')
  await expect(rows).toHaveCount(1)
  await chooseOption(filter, 'Невыгодные')
  await expect(page).toHaveURL(/deals=non_deals/)
  await expect(rows).toHaveCount(total - 1)
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toHaveCount(0)
  await page.reload()
  await expect(filter).toHaveText('Невыгодные')
  await expect(rows).toHaveCount(total - 1)
  await page.getByLabel('Поиск по названию или артикулу').fill('AirPods')
  await expect(rows).toHaveCount(1)
  await expect(rows).toContainText('AirPods')
  await page.getByRole('button', { name: 'Сбросить', exact: true }).click()
  await expect(filter).toHaveText('Все товары')
  await expect(page).toHaveURL(/\/cards$/)
  await expect(rows).toHaveCount(total)
})
