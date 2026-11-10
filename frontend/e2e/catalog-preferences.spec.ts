import { expect, test, type Page } from '@playwright/test'
import { selectMany } from './catalog-controls'

async function choose(page: Page, name: string, option: string) {
  await page.getByRole('combobox', { name, exact: true }).click()
  await page.getByRole('option', { name: option, exact: true }).click()
}

test('catalog options survive a fresh browser context; reset is permanent and links take precedence', async ({ page, browser }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/cards?fixture=catalog')
  await expect(page.getByRole('heading', { name: 'Товары', exact: true })).toBeVisible()
  await expect(page).toHaveTitle(/Price watch/i)
  await page.getByLabel('Поиск по названию или артикулу').fill('Наушники')
  await page.getByRole('checkbox', { name: 'Только в наличии' }).check()
  await page.getByRole('checkbox', { name: 'Сначала товары, участвующие в выгодных предложениях' }).uncheck()
  await choose(page, 'Участие в выгодных', 'Участвуют в выгодных')
  await selectMany(page, 'Маркетплейсы', ['Ozon', 'Wildberries'])
  await selectMany(page, 'Теги', ['Электроника', 'Для себя'])
  await page.getByRole('button', { name: 'Средняя', exact: true }).click()
  await page.getByRole('button', { name: 'Средняя', exact: true }).click()
  await page.getByRole('checkbox', { name: /Выбрать карточку Наушники Apple/ }).check()
  await page.getByRole('radio', { name: 'Сетка', exact: true }).click()
  const original = new URL(page.url()).searchParams
  const state = await page.context().storageState()
  await page.close()

  const context = await browser.newContext({ storageState: state, locale: 'ru-RU', viewport: { width: 1440, height: 900 } })
  const reopened = await context.newPage()
  reopened.on('pageerror', (error) => errors.push(error.message))
  try {
    await reopened.goto('/cards?fixture=catalog')
    await expect(reopened.getByLabel('Поиск по названию или артикулу')).toHaveValue('Наушники')
    await expect(reopened.getByRole('checkbox', { name: 'Только в наличии' })).toBeChecked()
    await expect(reopened.getByRole('checkbox', { name: 'Сначала товары, участвующие в выгодных предложениях' })).not.toBeChecked()
    await expect(reopened.getByRole('radio', { name: 'Сетка', exact: true })).toHaveAttribute('data-state', 'on')
    await expect(reopened.getByRole('combobox', { name: 'Участие в выгодных', exact: true })).toContainText('Участвуют в выгодных')
    await expect(reopened.getByRole('combobox', { name: 'Сортировка', exact: true })).toContainText('Средняя · по убыванию')
    const restored = new URL(reopened.url()).searchParams
    for (const key of ['q', 'stock', 'participationFirst', 'deals', 'markets', 'tags', 'sort', 'view']) {
      expect(restored.getAll(key)).toEqual(original.getAll(key))
    }
    await expect(reopened.getByRole('group', { name: 'Действия с выбранными карточками' })).toHaveCount(0)
    await reopened.getByRole('link', { name: 'Наушники Apple AirPods Pro 2', exact: true }).click()
    await reopened.getByRole('link', { name: 'К товарам', exact: true }).click()
    await expect(reopened.getByLabel('Поиск по названию или артикулу')).toHaveValue('Наушники')
    await reopened.screenshot({ path: '/tmp/price-watch-catalog-preferences.png' })
    await reopened.getByRole('button', { name: 'Сбросить', exact: true }).click()
    await reopened.goto('/cards')
    await expect(reopened.getByLabel('Поиск по названию или артикулу')).toHaveValue('')
    await expect(reopened.getByRole('checkbox', { name: 'Только в наличии' })).not.toBeChecked()
    await expect(reopened.getByRole('radio', { name: 'Сетка', exact: true })).toHaveAttribute('data-state', 'on')
    await reopened.goto('/cards?stock=1')
    await expect(reopened.getByRole('radio', { name: 'Список', exact: true })).toHaveAttribute('data-state', 'on')
    await expect(reopened.getByRole('checkbox', { name: 'Только в наличии' })).toBeChecked()
    expect(errors).toEqual([])
    await expect(reopened.locator('vite-error-overlay')).toHaveCount(0)
  } finally {
    await context.close()
  }
})

test('collapsed groups survive details and reload; selection stays temporary', async ({ page }) => {
  const url = '/cards?perf=100&shape=mixed&sort=title-asc'
  await page.goto(url)
  const toggle = page.getByRole('button', { name: /^(Раскрыть|Свернуть) группу Тестовая группа 1$/ })
  await expect(toggle).toHaveAttribute('aria-expanded', 'true')
  await page.getByRole('checkbox', { name: 'Выбрать карточку Тестовый товар 00000', exact: true }).check()
  await toggle.click()
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')
  await page.getByRole('link', { name: /^Тестовый товар/ }).first().click()
  await page.getByRole('link', { name: 'К товарам', exact: true }).click()
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByRole('group', { name: 'Действия с выбранными карточками' })).toHaveCount(0)
  await page.reload()
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')
  await toggle.click()
  await expect(toggle).toHaveAttribute('aria-expanded', 'true')
  await page.reload()
  await expect(toggle).toHaveAttribute('aria-expanded', 'true')
})

test('untagged filter survives reopening without becoming all tags', async ({ page }) => {
  await page.goto('/cards?fixture=catalog')
  await selectMany(page, 'Теги', [])
  await page.goto('/cards?fixture=catalog')
  await expect(page.getByRole('button', { name: 'Теги', exact: true })).toContainText('Без тегов')
  await expect(page.getByRole('link', { name: 'Конструктор LEGO Technic McLaren P1', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Наушники Apple AirPods Pro 2', exact: true })).toHaveCount(0)
})
