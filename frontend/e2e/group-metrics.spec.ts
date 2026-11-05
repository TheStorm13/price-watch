import { expect, test, type Page } from '@playwright/test'

async function choose(page: Page, name: string, value: string) {
  await page.getByRole('combobox', { name, exact: true }).click()
  await page.getByRole('option', { name: value, exact: true }).click()
  await expect(page.getByRole('combobox', { name, exact: true })).toHaveText(value)
  await expect(page.getByRole('combobox', { name, exact: true })).toHaveAttribute('aria-expanded', 'false')
}
function fixtureCard(externalId: string, marketplace: string, prices: number[], tag: string) {
  return { externalId, marketplace, title: `Fixture товар ${externalId}`, url: null, imageUrl: null,
    tags: [tag], createdAt: '2026-10-01T12:00:00Z', dealsEnabled: true,
    primaryExternalId: marketplace==='wildberries'?`${externalId}:1`:externalId,
    variants:[{externalId:marketplace==='wildberries'?`${externalId}:1`:externalId,url:null,history: prices.map((price, index) => ({ price: String(price), availability: 'in_stock', observedAt: `2026-10-0${index + 1}T12:00:00Z` })) }] }
}
async function importFixture(page: Page, document: object) {
  await page.getByLabel('Дополнительные действия').click()
  await page.getByRole('menuitem', { name: 'Импорт', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Импорт карточек и истории' })
  await dialog.locator('input[type="file"]').setInputFiles({ name: 'fixture.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(document)) })
  await expect(dialog.getByRole('button', { name: 'Импортировать', exact: true })).toBeEnabled()
  await dialog.getByRole('button', { name: 'Импортировать', exact: true }).click()
  await expect(dialog).toHaveCount(0)
}
const members = [{ marketplace: 'ozon', externalId: '901' }, { marketplace: 'wildberries', externalId: '902' }]

test('выгода и максимум видны после отключения участия, фильтр исключает товар', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()) })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/cards')
  await expect(page).toHaveTitle('Price watch')
  await importFixture(page, { version: 3, groups: [], cards: [fixtureCard('901', 'ozon', [100, 60, 70], 'savings'),
    fixtureCard('903', 'ozon', [100, 110], 'zero'), fixtureCard('904', 'ozon', [100], 'no-baseline')] })
  await page.getByLabel('Поиск карточек').fill('Fixture')
  await expect(page.locator('.cards-table__product').filter({ hasText: 'Fixture товар 903' }).locator('.catalog-savings__maximum')).toHaveText('0 ₽')
  await expect(page.locator('.cards-table__product').filter({ hasText: 'Fixture товар 904' }).locator('.catalog-savings__maximum')).toHaveText('—')
  const row = page.locator('.cards-table__product').filter({ hasText: 'Fixture товар 901' })
  await expect(row.locator('.deal-savings')).toHaveText('10 ₽')
  await expect(row.locator('.catalog-savings__maximum')).toHaveText('20 ₽')
  const sizes = await row.locator('.catalog-savings > span').evaluateAll(elements => elements.map(element => ({
    font: parseFloat(getComputedStyle(element).fontSize), top: element.getBoundingClientRect().top,
  })))
  expect(sizes[1].font).toBeLessThan(sizes[0].font)
  expect(sizes[1].top).toBeGreaterThan(sizes[0].top)
  const heading = page.getByRole('columnheader', { name: /Выгода \/\s*Максимальная выгода/ })
  await heading.getByRole('button').click()
  await expect(heading).toHaveAttribute('aria-sort', 'ascending')
  await row.getByRole('button', { name: /Действия с карточкой/ }).click()
  await page.getByRole('menuitem', { name: 'Не учитывать в выгодных предложениях' }).click()
  await expect(row).toContainText('Не участвует в выгодных')
  await expect(row.locator('.deal-savings')).toHaveText('10 ₽')
  await expect(row.locator('.catalog-savings__maximum')).toHaveText('20 ₽')
  await choose(page, 'Выгодность', 'Выгодные')
  await expect(row).toHaveCount(0)
  await choose(page, 'Выгодность', 'Все')
  await expect(row.locator('.deal-savings')).toHaveText('10 ₽')
  await expect(page.locator('vite-error-overlay')).toHaveCount(0)
  expect(errors).toEqual([])
})

test('границы папки, теги и одинаковые интервалы сохраняются при раскрытии и смене вида', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.setViewportSize({ width: 1536, height: 1000 })
  await page.goto('/cards')
  const representative = fixtureCard('901', 'ozon', [100, 70], 'Очень длинный тег представителя группы')
  representative.tags.push('Ещё один длинный тег для проверки ширины')
  const name = 'Fixture группа с длинным названием для проверки переноса текста'
  await importFixture(page, { version: 3, cards: [representative,
    fixtureCard('902', 'wildberries', [200, 110], 'other'),
    fixtureCard('903', 'ozon', [60, 80], 'standalone'),
    fixtureCard('904', 'ozon', [60, 90], 'standalone')],
    groups: [{ name, cards: members }, { name: 'Fixture пустая группа', cards: [] }] })
  await page.getByLabel('Поиск карточек').fill('Fixture')
  const group = page.locator('.cards-table__group').filter({ hasText: name })
  const toggle = group.locator('.product-group__toggle')
  await expect(group).toContainText('Группа · 2 товара')
  await expect(group.locator('time')).toHaveCount(0)
  await expect(group.locator('.tag')).toHaveText(representative.tags)
  const empty = page.locator('.cards-table__group').filter({ hasText: 'Fixture пустая группа' })
  await expect(empty).toHaveAttribute('data-block-end', 'true')
  await expect(empty).toContainText('Группа · 0 товаров')
  for (const width of [1536, 1024]) {
    await page.setViewportSize({ width, height: 1000 })
    await expect(group.locator('td').first()).toHaveCSS('border-top-width', '8px')
    const lastMember = page.locator('.cards-table__nested').last()
    await expect(lastMember).toHaveAttribute('data-block-end', 'true')
    await expect(lastMember.locator('td').first()).toHaveCSS('border-bottom-left-radius', '10px')
    await expect(lastMember.locator('td').first()).toHaveCSS('border-bottom-color', 'rgb(228, 231, 236)')
    for (const row of await page.locator('.cards-table__product:not(.cards-table__nested)').all()) {
      await expect(row.locator('td').first()).toHaveCSS('border-top-width', '8px')
      await expect(row.locator('td').first()).toHaveCSS('border-bottom-left-radius', '10px')
    }
    const tagsFit = await group.locator('.tag-list').evaluate(element => {
      const bounds = element.getBoundingClientRect()
      return [...element.children].every(tag => tag.getBoundingClientRect().right <= bounds.right + 1)
    })
    expect(tagsFit).toBe(true)
    await toggle.focus()
    await page.keyboard.press('Enter')
    await expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await expect(group).toHaveAttribute('data-block-end', 'true')
    await expect(page.locator('.cards-table__nested')).toHaveCount(0)
    await expect(group.locator('td').first()).toHaveCSS('border-bottom-left-radius', '10px')
    await page.keyboard.press('Enter')
    await expect(page.locator('.cards-table__nested')).toHaveCount(2)
  }
  await page.getByRole('radio', { name: 'Сетка', exact: true }).click()
  const gridGroup = page.locator('.cards-grid__group').filter({ hasText: name })
  await expect(gridGroup.locator('time')).toHaveCount(0)
  await expect(gridGroup.locator('.tag')).toHaveText(representative.tags)
  const nested = page.locator('.virtual-grid-row[data-group-member][data-block-end]')
  await expect(nested.locator('.cards-grid')).toHaveCSS('border-bottom-left-radius', '10px')
  await expect(nested).toHaveCSS('padding-bottom', '8px')
  await gridGroup.locator('.product-group__toggle').click()
  await expect(page.locator('.cards-grid--nested')).toHaveCount(0)
  await expect(gridGroup.locator('.product-group__header')).toHaveCSS('border-bottom-left-radius', '10px')
  await expect(page.locator('vite-error-overlay')).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  expect(errors).toEqual([])
})

test('группа фильтруется по представителю и чередуется с карточками в обоих видах', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()) })
  await page.setViewportSize({ width: 1536, height: 1000 })
  await page.goto('/cards')
  await expect(page).toHaveTitle('Price watch')
  await expect(page.getByRole('heading', { name: 'Карточки', exact: true })).toBeVisible()
  await expect(page.locator('vite-error-overlay')).toHaveCount(0)
  await importFixture(page, { version: 3, cards: [fixtureCard('901', 'ozon', [60, 70], 'cheap'),
    fixtureCard('902', 'wildberries', [40, 110], 'other'), fixtureCard('903', 'ozon', [60, 80], 'standalone'),
    fixtureCard('904', 'wildberries', [60, 90], 'second')], groups: [
    { name: 'Fixture A', tags: ['own'], cards: members },
    { name: 'Fixture B', cards: [{ marketplace: 'wildberries', externalId: '904' }] },
  ] })
  await page.getByLabel('Поиск карточек').fill('Fixture')
  await choose(page, 'Сортировка', 'Сначала дешевле')
  const topRows = page.locator('.cards-table__group, .cards-table__product:not(.cards-table__nested)')
  await expect(topRows).toHaveCount(3)
  await expect(topRows.nth(0)).toContainText('Fixture A')
  await expect(topRows.nth(1)).toContainText('Fixture товар 903')
  await expect(topRows.nth(2)).toContainText('Fixture B')
  const a = page.locator('.cards-table__group').filter({ hasText: 'Fixture A' })
  await expect(a.locator('td').nth(4)).toHaveText('60 ₽') // not the other member's historical 40
  await expect(a.locator('td').nth(5)).toHaveText('60 ₽')
  await choose(page, 'Маркетплейс', 'Wildberries')
  await expect(page.locator('.cards-table__group')).toHaveCount(1)
  await expect(page.locator('.cards-table__group')).toContainText('Fixture B')
  await choose(page, 'Маркетплейс', 'Все маркетплейсы')
  await page.getByRole('combobox', { name: 'Тег', exact: true }).click()
  await expect(page.getByRole('option', { name: 'other', exact: true })).toHaveCount(0)
  await expect(page.getByRole('option', { name: 'own', exact: true })).toHaveCount(0)
  await page.keyboard.press('Escape')
  await page.getByLabel('Поиск карточек').fill('Fixture товар 902')
  await expect(page.getByText('По выбранным условиям ничего не найдено')).toBeVisible()
  await page.getByLabel('Поиск карточек').fill('Fixture')
  await choose(page, 'Тег', 'cheap')
  await expect(page.locator('.cards-table__group')).toHaveCount(1)
  await expect(page.locator('.cards-table__nested')).toHaveCount(2) // complete membership
  await choose(page, 'Тег', 'Все теги')
  await page.getByRole('radio', { name: 'Сетка' }).click()
  const grid = page.getByRole('list', { name: 'Отслеживаемые карточки маркетплейсов' })
  await expect(grid.locator(':scope > .cards-grid__group, :scope > .virtual-grid-row:not([data-group-member]) .cards-grid__item')).toHaveCount(3)
  await expect(grid.locator(':scope > .cards-grid__group, :scope > .virtual-grid-row:not([data-group-member]) .cards-grid__item').nth(0)).toContainText('Fixture A')
  await expect(grid.locator(':scope > .cards-grid__group, :scope > .virtual-grid-row:not([data-group-member]) .cards-grid__item').nth(1)).toContainText('Fixture товар 903')
  await expect(grid.locator(':scope > .cards-grid__group, :scope > .virtual-grid-row:not([data-group-member]) .cards-grid__item').nth(2)).toContainText('Fixture B')
  await choose(page, 'Сортировка', 'Сначала дороже')
  await expect(grid.locator(':scope > .cards-grid__group, :scope > .virtual-grid-row:not([data-group-member]) .cards-grid__item').nth(0)).toContainText('Fixture B')
  await expect(grid.locator(':scope > .cards-grid__group, :scope > .virtual-grid-row:not([data-group-member]) .cards-grid__item').nth(2)).toContainText('Fixture A')
  for (const width of [1024, 1536]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  }
  expect(errors).toEqual([])
})

test('выгодный участник даёт приоритет без подмены полей и фильтра выгодности группы', async ({ page }) => {
  await page.goto('/cards')
  await expect(page).toHaveTitle('Price watch')
  await expect(page.getByRole('heading', { name: 'Карточки', exact: true })).toBeVisible()
  await expect(page.locator('vite-error-overlay')).toHaveCount(0)
  await importFixture(page, { version: 3,
    cards: [fixtureCard('901', 'ozon', [60, 70], 'cheap'), fixtureCard('902', 'wildberries', [200, 110], 'other'),
      fixtureCard('903', 'ozon', [10, 20], 'standalone')], groups: [{ name: 'Fixture A', cards: members }] })
  await page.getByLabel('Поиск карточек').fill('Fixture')
  await choose(page, 'Сортировка', 'Сначала дешевле')
  const rows = page.locator('.cards-table__group, .cards-table__product:not(.cards-table__nested)')
  await expect(rows.nth(0)).toContainText('Fixture A') // priority beats the cheaper standalone
  await expect(rows.nth(0)).toContainText('Есть выгодный товар внутри')
  await expect(rows.nth(0).locator('td').nth(6).locator('.catalog-savings > span').first()).toHaveText('Сейчас не выгодно')
  await choose(page, 'Выгодность', 'Выгодные')
  await expect(page.getByRole('combobox', { name: 'Выгодность' })).toHaveText('Выгодные')
  await expect(page.getByText('По выбранным условиям ничего не найдено')).toBeVisible()
  await choose(page, 'Выгодность', 'Не выгодные')
  await expect(rows).toHaveCount(2)
  await expect(rows.nth(0)).toContainText('Fixture A')
})

test('изменение участия и удаление представителя сразу обновляют поля группы', async ({ page }) => {
  await page.goto('/cards')
  await expect(page).toHaveTitle('Price watch')
  await expect(page.getByRole('heading', { name: 'Карточки', exact: true })).toBeVisible()
  await expect(page.locator('vite-error-overlay')).toHaveCount(0)
  await importFixture(page, { version: 3,
    cards: [fixtureCard('901', 'ozon', [100, 70], 'cheap'), fixtureCard('902', 'wildberries', [200, 110], 'other')],
    groups: [{ name: 'Fixture A', cards: members }] })
  await page.getByLabel('Поиск карточек').fill('Fixture')
  const group = page.locator('.cards-table__group')
  await expect(group.locator('td').nth(6).locator('.deal-savings')).toHaveText('30 ₽')
  const representative = page.locator('.cards-table__nested').filter({ hasText: 'Fixture товар 901' })
  await representative.getByRole('button', { name: /Действия с карточкой/ }).click()
  await page.getByRole('menuitem', { name: 'Не учитывать в выгодных предложениях' }).click()
  await expect(group).toContainText('Не участвует в выгодных')
  await expect(group).toContainText('Есть выгодный товар внутри')
  await expect(group.locator('td').nth(6).locator('.deal-savings')).toHaveText('30 ₽')
  await representative.getByRole('button', { name: /Действия с карточкой/ }).click()
  await page.getByRole('menuitem', { name: 'Удалить карточку' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Удалить', exact: true }).click()
  await expect(group.locator('td').nth(3)).toHaveText('110 ₽')
  await expect(group.locator('td').nth(5)).toHaveText('200 ₽')
  await expect(group.locator('td').nth(6).locator('.deal-savings')).toHaveText('90 ₽')
  await expect(group.locator('td').nth(2)).toContainText('Wildberries')
  await expect(group).not.toContainText('Не участвует в выгодных')
})

test('десятичные цены сортируются точно и отображаются в целых рублях', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()) })
  await page.goto('/cards')
  await expect(page.getByRole('heading', { name: 'Карточки', exact: true })).toBeVisible()
  const createdAt = new Date().toISOString()
  await importFixture(page, { version: 3, groups: [], cards: [
    { marketplace: 'ozon', externalId: '9901', title: 'Decimal A', url: null, dealsEnabled: true, createdAt,
      primaryExternalId:'9901',variants:[{externalId:'9901',url:null,history: [{ price: '9.90', availability: 'in_stock', observedAt: createdAt }]}] },
    { marketplace: 'wildberries', externalId: '9902', title: 'Decimal B', url: null, dealsEnabled: true, createdAt,
      primaryExternalId:'9902:1',variants:[{externalId:'9902:1',url:null,history: [{ price: '10.00', availability: 'in_stock', observedAt: createdAt }]}] },
  ] })
  await page.getByLabel('Поиск карточек').fill('Decimal')
  await choose(page, 'Сортировка', 'Сначала дешевле')
  const rows = page.locator('.cards-table__product:not(.cards-table__nested)')
  await expect(rows).toHaveCount(2)
  await expect(rows.nth(0)).toContainText('Decimal A')
  await expect(rows.nth(0)).toContainText('10 ₽')
  await expect(rows.nth(1)).toContainText('Decimal B')
  await expect(rows.nth(1)).toContainText('10 ₽')
  await choose(page, 'Сортировка', 'Сначала дороже')
  await expect(rows.nth(0)).toContainText('Decimal B')
  await choose(page, 'Сортировка', 'Сначала дешевле')
  await page.getByRole('radio', { name: 'Сетка' }).click()
  const tiles = page.getByRole('list', { name: 'Отслеживаемые карточки маркетплейсов' }).locator('.cards-grid__item')
  await expect(tiles.nth(0)).toContainText('Decimal A')
  await expect(tiles.nth(0)).toContainText('10 ₽')
  await expect(page.locator('vite-error-overlay')).toHaveCount(0)
  await tiles.nth(0).getByRole('link').click()
  await expect(page.getByRole('heading', { name: 'Decimal A', exact: true })).toBeVisible()
  await expect(page.locator('.price-summary__primary')).toContainText('10 ₽')
  await expect(page.locator('.history-table tbody tr').first()).toContainText('10 ₽')
  const axisTicks = page.locator('.recharts-yAxis-tick-labels .recharts-cartesian-axis-tick-value')
  await expect(axisTicks.first()).toBeVisible()
  const axisLabels = await axisTicks.allTextContents()
  expect(axisLabels.every((label) => !label.includes(','))).toBe(true)
  expect(new Set(axisLabels).size).toBe(axisLabels.length)
  await page.locator('.recharts-line-dots .recharts-dot').first().hover()
  await expect(page.locator('.recharts-tooltip-wrapper')).toContainText('10 ₽')
  expect(errors).toEqual([])
})
