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
    history: prices.map((price, index) => ({ price: String(price), availability: 'in_stock', observedAt: `2026-10-0${index + 1}T12:00:00Z` })) }
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

test('группа фильтруется по представителю и чередуется с карточками в обоих видах', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()) })
  await page.setViewportSize({ width: 1536, height: 1000 })
  await page.goto('/cards')
  await expect(page).toHaveTitle('price-watch')
  await expect(page.getByRole('heading', { name: 'Карточки', exact: true })).toBeVisible()
  await expect(page.locator('vite-error-overlay')).toHaveCount(0)
  await importFixture(page, { version: 2, cards: [fixtureCard('901', 'ozon', [60, 70], 'cheap'),
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
  await page.screenshot({ path: '/tmp/price-watch-group-metrics-list.png' })
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
    await page.screenshot({ path: `/tmp/price-watch-group-metrics-grid-${width}.png` })
  }
  expect(errors).toEqual([])
})

test('выгодный участник даёт приоритет без подмены полей и фильтра выгодности группы', async ({ page }) => {
  await page.goto('/cards')
  await expect(page).toHaveTitle('price-watch')
  await expect(page.getByRole('heading', { name: 'Карточки', exact: true })).toBeVisible()
  await expect(page.locator('vite-error-overlay')).toHaveCount(0)
  await importFixture(page, { version: 2,
    cards: [fixtureCard('901', 'ozon', [60, 70], 'cheap'), fixtureCard('902', 'wildberries', [200, 110], 'other'),
      fixtureCard('903', 'ozon', [10, 20], 'standalone')], groups: [{ name: 'Fixture A', cards: members }] })
  await page.getByLabel('Поиск карточек').fill('Fixture')
  await choose(page, 'Сортировка', 'Сначала дешевле')
  const rows = page.locator('.cards-table__group, .cards-table__product:not(.cards-table__nested)')
  await expect(rows.nth(0)).toContainText('Fixture A') // priority beats the cheaper standalone
  await expect(rows.nth(0)).toContainText('Есть выгодный товар внутри')
  await expect(rows.nth(0).locator('td').nth(6)).toHaveText('Сейчас не выгодно')
  await page.getByRole('checkbox', { name: 'Выгодные предложения' }).click()
  await expect(page.getByRole('checkbox', { name: 'Выгодные предложения' })).toBeChecked()
  await expect(page.getByText('По выбранным условиям ничего не найдено')).toBeVisible()
})

test('изменение участия и удаление представителя сразу обновляют поля группы', async ({ page }) => {
  await page.goto('/cards')
  await expect(page).toHaveTitle('price-watch')
  await expect(page.getByRole('heading', { name: 'Карточки', exact: true })).toBeVisible()
  await expect(page.locator('vite-error-overlay')).toHaveCount(0)
  await importFixture(page, { version: 2,
    cards: [fixtureCard('901', 'ozon', [100, 70], 'cheap'), fixtureCard('902', 'wildberries', [200, 110], 'other')],
    groups: [{ name: 'Fixture A', cards: members }] })
  await page.getByLabel('Поиск карточек').fill('Fixture')
  const group = page.locator('.cards-table__group')
  await expect(group.locator('td').nth(6)).toHaveText('30 ₽')
  const representative = page.locator('.cards-table__nested').filter({ hasText: 'Fixture товар 901' })
  await representative.getByRole('button', { name: /Действия с карточкой/ }).click()
  await page.getByRole('menuitem', { name: 'Не учитывать в выгодных предложениях' }).click()
  await expect(group).toContainText('Не участвует в выгодных')
  await expect(group).toContainText('Есть выгодный товар внутри')
  await expect(group.locator('td').nth(6)).toHaveText('Сейчас не выгодно')
  await representative.getByRole('button', { name: /Действия с карточкой/ }).click()
  await page.getByRole('menuitem', { name: 'Удалить карточку' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Удалить', exact: true }).click()
  await expect(group.locator('td').nth(3)).toHaveText('110 ₽')
  await expect(group.locator('td').nth(5)).toHaveText('200 ₽')
  await expect(group.locator('td').nth(6)).toHaveText('90 ₽')
  await expect(group.locator('td').nth(2)).toContainText('Wildberries')
  await expect(group).not.toContainText('Не участвует в выгодных')
})

test('десятичные цены сортируются численно и сохраняют копейки в списке и плитке', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()) })
  await page.goto('/cards')
  await expect(page.getByRole('heading', { name: 'Карточки', exact: true })).toBeVisible()
  const createdAt = new Date().toISOString()
  await importFixture(page, { version: 2, groups: [], cards: [
    { marketplace: 'ozon', externalId: '9901', title: 'Decimal A', url: null, dealsEnabled: true, createdAt,
      history: [{ price: '9.90', availability: 'in_stock', observedAt: createdAt }] },
    { marketplace: 'wildberries', externalId: '9902', title: 'Decimal B', url: null, dealsEnabled: true, createdAt,
      history: [{ price: '10.00', availability: 'in_stock', observedAt: createdAt }] },
  ] })
  await page.getByLabel('Поиск карточек').fill('Decimal')
  await choose(page, 'Сортировка', 'Сначала дешевле')
  const rows = page.locator('.cards-table__product:not(.cards-table__nested)')
  await expect(rows).toHaveCount(2)
  await expect(rows.nth(0)).toContainText('Decimal A')
  await expect(rows.nth(0)).toContainText('9,90 ₽')
  await expect(rows.nth(1)).toContainText('Decimal B')
  await page.getByRole('radio', { name: 'Сетка' }).click()
  const tiles = page.getByRole('list', { name: 'Отслеживаемые карточки маркетплейсов' }).locator('.cards-grid__item')
  await expect(tiles.nth(0)).toContainText('Decimal A')
  await expect(tiles.nth(0)).toContainText('9,90 ₽')
  await expect(page.locator('vite-error-overlay')).toHaveCount(0)
  await page.screenshot({ path: '/tmp/price-watch-model-decimal-grid.png', fullPage: true })
  await tiles.nth(0).getByRole('link').click()
  await expect(page.getByRole('heading', { name: 'Decimal A', exact: true })).toBeVisible()
  await page.locator('.recharts-line-dots .recharts-dot').first().hover()
  await expect(page.locator('.recharts-tooltip-wrapper')).toContainText('9,90 ₽')
  await page.screenshot({ path: '/tmp/price-watch-model-decimal-chart.png', fullPage: true })
  expect(errors).toEqual([])
})
