import { expect, test, type Page } from '@playwright/test'

async function catalog(page: Page) {
  await page.goto('/cards')
  await expect(page.locator('.cards-table__product').first()).toBeVisible()
}

test('контекст каталога, скрытые артикулы и клавиатурная ссылка сохраняются', async ({ page }) => {
  const url = '/cards?q=1604900984&markets=ozon&sort=price-desc&view=grid'
  await page.goto(url)
  const tile = page.locator('.cards-grid__item')
  await expect(tile).toHaveCount(1)
  await expect(tile).not.toContainText('1604900984')
  expect((await tile.boundingBox())!.width).toBeLessThanOrEqual(280)
  await tile.getByRole('link').click()
  await expect(page.getByText('ID 1604900984', { exact: true })).toBeVisible()
  await page.getByRole('radio', { name: '7 дней', exact: true }).click()
  await page.getByRole('link', { name: 'К товарам', exact: true }).click()
  await expect(page).toHaveURL(url)
  await page.getByRole('radio', { name: 'Список', exact: true }).click()
  const row = page.locator('.cards-table__product')
  await expect(row).not.toContainText('1604900984')
  await row.getByRole('checkbox').check()
  await expect(page).not.toHaveURL(/cards\/1/)
  const link = row.getByRole('link', { name: 'Смартфон Samsung Galaxy S24', exact: true })
  await link.focus()
  await expect(link).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/cards\/1$/)
  const direct = await page.context().newPage()
  await direct.goto('/cards/1')
  await direct.getByRole('link', { name: 'К товарам', exact: true }).click()
  await expect(direct).toHaveURL(url.replace('&view=grid', ''))
  await expect(direct.getByRole('radio', { name: 'Список', exact: true })).toBeChecked()
  await expect(direct.getByLabel('Поиск по названию или артикулу')).toHaveValue('1604900984')
  await direct.close()
})

for (const section of ['chart', 'history'] as const) {
  test(`ошибка ${section} не скрывает доступные разделы, повтор восстанавливает данные`, async ({ page }) => {
    await catalog(page)
    await page.evaluate(async (target) => {
      const { api } = await import('/src/api/client.ts')
      const key = target === 'chart' ? 'getChart' : 'getHistory'
      const original = api[key].bind(api)
      let calls = 0
      // First request plus the configured query retry fail; user retry succeeds.
      Object.assign(api, { [key]: async (...args: [number, number]) => {
        if (++calls <= 2) throw new Error('Синтетический отказ раздела')
        return original(...args)
      } })
    }, section)
    await page.locator('.cards-table__product').first().getByRole('link').click()
    await expect(page.getByRole('heading', { name: 'Смартфон Samsung Galaxy S24', exact: true })).toBeVisible()
    const error = page.getByRole('alert').filter({ hasText: section === 'chart' ? 'Не удалось загрузить график' : 'Не удалось загрузить измерения' })
    await expect(error).toBeVisible()
    if (section === 'chart') await expect(page.locator('.history-table tbody tr')).toHaveCount(10)
    else await expect(page.getByLabel('График цен вариантов товара')).toBeVisible()
    await error.getByRole('button', { name: 'Повторить' }).click()
    await expect(error).toHaveCount(0)
    await expect(page.locator('.history-table tbody tr')).toHaveCount(10)
    await expect(page.getByLabel('График цен вариантов товара')).toBeVisible()
  })
}

test('ожидание графика и смена периода оставляют шапку доступной; 404 отличается от отказа раздела', async ({ page }) => {
  await catalog(page)
  await page.evaluate(async () => {
    const { api } = await import('/src/api/client.ts')
    api.getChart = () => new Promise(() => {})
  })
  await page.locator('.cards-table__product').first().getByRole('link').click()
  await expect(page.getByRole('heading', { name: 'Смартфон Samsung Galaxy S24', exact: true })).toBeVisible()
  await expect(page.getByLabel('Загрузка графика')).toBeVisible()
  await page.getByRole('radio', { name: '7 дней', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Смартфон Samsung Galaxy S24', exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'К товарам' }).click()
  await page.evaluate(async () => {
    const { api, ApiError } = await import('/src/api/client.ts')
    api.getCard = async () => { throw new ApiError('Нет карточки', 'card_not_found') }
  })
  await page.locator('.cards-table__product').nth(1).getByRole('link').click()
  await expect(page.getByText('Товар не найден', { exact: true })).toBeVisible()
})

test('выбор плиток общий со списком и включает участников групп', async ({ page }) => {
  await catalog(page)
  await page.locator('.cards-table__product').first().getByRole('checkbox').check()
  await page.getByRole('radio', { name: 'Сетка', exact: true }).click()
  const tiles = page.locator('.cards-grid__item')
  await expect(tiles.first().getByRole('checkbox')).toBeChecked()
  await expect(tiles.first()).toHaveClass(/is-selected/)
  await tiles.nth(1).getByRole('checkbox').check()
  const bulk = page.getByRole('group', { name: 'Действия с выбранными карточками' })
  await expect(bulk).toContainText('Выбрано: 2')
  await page.getByRole('radio', { name: 'Список', exact: true }).click()
  await expect(page.locator('.cards-table__product').nth(1).getByRole('checkbox')).toBeChecked()
  await bulk.getByRole('button', { name: 'Создать группу', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Создать группу' })
  await dialog.getByRole('textbox', { name: 'Название', exact: true }).fill('Группа выбора')
  await dialog.getByRole('button', { name: 'Сохранить', exact: true }).click()
  await expect(dialog).toHaveCount(0)
  await page.getByRole('radio', { name: 'Сетка', exact: true }).click()
  const nested = page.locator('.cards-grid--nested .cards-grid__item')
  await expect(nested).toHaveCount(2)
  await nested.first().getByRole('checkbox').check()
  await bulk.getByRole('button', { name: 'Удалить выбранные' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Отмена' }).click()
  await expect(nested.first().getByRole('checkbox')).toBeChecked()
})

test('наличие и меню закреплены при прокрутке узкой таблицы', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 700 })
  await catalog(page)
  const scroll = page.locator('.cards-table').locator('..')
  for (const fraction of [0, .5, 1]) {
    await scroll.evaluate((el, f) => { el.scrollLeft = (el.scrollWidth - el.clientWidth) * f }, fraction)
    const bounds = (await scroll.boundingBox())!
    for (const row of await page.locator('.cards-table__product').all()) {
      const last = (await row.locator('td').last().boundingBox())!
      const availability = (await row.locator('td').nth(7).boundingBox())!
      expect(last.x + last.width).toBeLessThanOrEqual(bounds.x + bounds.width + 1)
      expect(availability.x).toBeGreaterThanOrEqual(bounds.x)
      expect(availability.x + availability.width).toBeLessThanOrEqual(last.x + 1)
    }
  }
})

test('названия и зоны плиток выровнены, теги целые, артикулы скрыты и безымянный товар доступен', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  const { uiFixture } = await import('./uiFixtures')
  await uiFixture(page)
  for (const width of [1024, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    await page.getByRole('radio', { name: 'Список', exact: true }).click()
    const offsets = await page.locator('.cards-table__product').evaluateAll((rows) => rows.map((row) => row.querySelector('.card-identity strong')!.getBoundingClientRect().top - row.getBoundingClientRect().top))
    expect(Math.max(...offsets) - Math.min(...offsets)).toBeLessThanOrEqual(1)
    await expect(page.locator('.table-surface')).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)')
    for (const image of await page.locator('.cards-table__product img').all()) {
      await expect(image).toBeVisible()
      const geometry = await image.evaluate(element => {
        const image = element as HTMLImageElement
        const box = image.getBoundingClientRect()
        const cell = image.closest('td')!
        const cellStyle = getComputedStyle(cell)
        const thumbnail = image.parentElement!.getBoundingClientRect()
        const bounds = cell.getBoundingClientRect()
        return { radius: parseFloat(getComputedStyle(image).borderRadius), ratio: box.width / box.height,
          naturalRatio: image.naturalWidth / image.naturalHeight,
          top: thumbnail.top - bounds.top - parseFloat(cellStyle.borderTopWidth),
          bottom: bounds.bottom - thumbnail.bottom - parseFloat(cellStyle.borderBottomWidth) }
      })
      expect(geometry.radius).toBeGreaterThanOrEqual(8)
      expect(geometry.ratio).toBeCloseTo(geometry.naturalRatio, 1)
      expect(geometry.top).toBeCloseTo(4, 0)
      // A taller title/tag block may add space below the fixed-size thumbnail.
      expect(geometry.bottom).toBeGreaterThanOrEqual(4)
      expect(geometry.bottom).toBeLessThanOrEqual(8)
    }
    await expect(page.locator('.cards-table')).not.toContainText('ID:')
    await expect(page.getByRole('link', { name: 'Без названия', exact: true })).toBeVisible()
    await page.getByRole('radio', { name: 'Сетка', exact: true }).click()
    const tiles = page.locator('.cards-grid__item')
    for (const image of await tiles.locator('img').all()) await expect(image).toHaveCSS('border-top-left-radius', '8px')
    const geometry = await tiles.evaluateAll((items) => items.map((tile) => {
      const top = tile.getBoundingClientRect().top
      return ['.cards-grid__media', '.cards-grid__title', '.cards-grid__tags', '.cards-grid__prices', 'time'].map((selector) => tile.querySelector(selector)!.getBoundingClientRect().top - top)
    }))
    for (let index = 0; index < geometry[0].length; index++) {
      const positions = geometry.map((g) => g[index])
      expect(Math.max(...positions) - Math.min(...positions)).toBeLessThanOrEqual(1)
    }
    for (const tag of await tiles.locator('.tag').all()) {
      const bounds = (await tag.boundingBox())!
      const parent = (await tag.locator('..').boundingBox())!
      expect(bounds.x).toBeGreaterThanOrEqual(parent.x)
      expect(bounds.x + bounds.width).toBeLessThanOrEqual(parent.x + parent.width + 1)
      expect(await tag.getAttribute('title')).toBe(await tag.textContent())
    }
    for (const tile of await tiles.all()) {
      expect((await tile.boundingBox())!.width).toBeLessThanOrEqual(280)
      for (const [index, price] of (await tile.locator('dd').all()).entries()) {
        const font = await price.evaluate((e) => parseFloat(getComputedStyle(e).fontSize))
        expect(font).toBe(index === 3 && ['Нет выгоды', '—'].includes(await price.innerText()) ? 13 : 14)
      }
    }
    await expect(page.locator('.cards-grid__id')).toHaveCount(0)
  }
  expect(errors).toEqual([])
})

test('длинные названия, крупные цены и действия форм помещаются в desktop-окне', async ({ page }) => {
  await page.route('**/src/api/mockApi.ts*', async (route) => {
    const response = await route.fetch()
    await route.fulfill({ response, body: await response.text() + `
const largeCard = mockApi.getCard.bind(mockApi), largeHistory = mockApi.getHistory.bind(mockApi);
mockApi.getCard = async id => ({...await largeCard(id),title:'Очень длинное название товара с подробным описанием комплектации и характеристик выбранной модели',currentPrice:'123456789.12',dealsEnabled:false});
mockApi.getHistory = async (...args) => {const data=await largeHistory(...args);return {...data,statistics:{...data.statistics,minimumPrice:'123456789.12',maximumPrice:'987654321.98'}}};
` })
  })
  await page.goto('/cards/1')
  for (const width of [1024, 1440, 1920]) {
    await page.setViewportSize({ width, height: width === 1024 ? 700 : 900 })
    await expect(page.getByRole('heading', { name: /Очень длинное название товара/ })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    const actions = (await page.locator('.detail-header__info > .page-actions').boundingBox())!
    const heading = (await page.getByRole('heading', { name: /Очень длинное название товара/ }).boundingBox())!
    expect(actions.y >= heading.y + heading.height || actions.x >= heading.x + heading.width).toBe(true)
  }
  await page.setViewportSize({ width: 1024, height: 700 })
  await page.getByRole('link', { name: 'К товарам' }).click()
  const create = page.getByRole('button', { name: 'Создать группу', exact: true })
  await create.click()
  const dialog = page.getByRole('dialog', { name: 'Создать группу' })
  await dialog.getByRole('button', { name: 'Сохранить', exact: true }).click()
  await expect(dialog.getByRole('alert')).toBeVisible()
  for (const name of ['Сохранить', 'Отмена']) await expect(dialog.getByRole('button', { name, exact: true })).toBeInViewport()
  await dialog.getByRole('textbox', { name: 'Название', exact: true }).fill('Длинное название группы для проверки выравнивания и переноса текста в узкой колонке каталога')
  await dialog.getByRole('checkbox').first().check()
  await dialog.getByRole('button', { name: 'Сохранить', exact: true }).click()
  await expect(dialog).toHaveCount(0)
  const group = page.locator('.cards-table__group')
  const title = (await group.locator('.product-group__toggle').boundingBox())!
  const cell = (await group.locator('td').nth(1).boundingBox())!
  expect(title.x + title.width).toBeLessThanOrEqual(cell.x + cell.width + 1)
  await page.getByRole('button', { name: /Изменить группу/ }).click()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: /Изменить группу/ })).toBeFocused()
})
