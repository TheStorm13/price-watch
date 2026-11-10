import { expect, test } from '@playwright/test'

test('Ozon: разные артикулы образуют одну карточку с цветами, размерами и главным вариантом', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  const now = new Date().toISOString()
  const seed = '2936650207'
  const skus = [seed, '2936649523', '2936649566', '2936649611', '2936649722', '2936649286',
    '2936649562', '2936649905', '2936646722', '2936649144', '2936649891', '2936649395']
  const sizes = ['42', '40', '41', '43', '44', '45']
  const image = (color: string) => `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="${color}"/></svg>`)}`
  const document = { version: 3, cards: [{ marketplace: 'ozon', externalId: seed, title: 'Кеды Thomas Munz',
    url: `https://www.ozon.ru/product/${seed}/`, createdAt: now, dealsEnabled: true, primaryExternalId: seed,
    variants: skus.map((sku, i) => ({ externalId: sku, title: 'Кеды Thomas Munz', productTitle: 'Кеды Thomas Munz',
      url: `https://www.ozon.ru/product/${sku}/`, imageUrl: image(i < 6 ? 'brown' : 'black'), updatedAt: now,
      options: { Цвет: i < 6 ? 'Коричневый' : 'Чёрный', Размер: sizes[i % 6] },
      history: [{ price: String(100 + i), availability: 'in_stock', observedAt: now }],
    })),
  }] }
  await page.goto('/cards')
  await expect(page).toHaveTitle('Price watch')
  await page.getByRole('button', { name: 'Настройки', exact: true }).click()
  await page.getByRole('dialog', { name: 'Настройки', exact: true }).getByRole('button', { name: 'Импорт', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Импорт товаров' })
  await dialog.locator('input[type="file"]').setInputFiles({ name: 'ozon.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(document)) })
  await expect(dialog).toContainText('Добавлено: 1')
  await dialog.getByRole('button', { name: 'Импортировать' }).click()
  await page.getByRole('link', { name: 'Кеды Thomas Munz', exact: true }).click()
  const variants = page.getByRole('region', { name: 'Варианты товара' })
  await expect(variants.getByRole('row')).toHaveCount(13)
  const trackingBoxes = variants.getByRole('checkbox')
  await expect(trackingBoxes.filter({ visible: true })).toHaveCount(12)
  await expect(variants.getByRole('checkbox', { name: 'Отслеживать: Цвет: Коричневый · Размер: 42', exact: true })).toBeChecked()
  await expect(variants.getByRole('checkbox', { name: 'Отслеживать: Цвет: Коричневый · Размер: 42', exact: true })).toBeDisabled()
  const black = variants.getByRole('checkbox', { name: 'Отслеживать: Цвет: Чёрный · Размер: 42', exact: true })
  await expect(black).not.toBeChecked()
  await black.click()
  await expect(black).toBeChecked()
  await variants.getByRole('button', { name: 'Выключить остальные' }).click()
  await expect(black).not.toBeChecked()
  await variants.getByRole('button', { name: 'Включить остальные' }).click()
  await expect(black).toBeChecked()
  await variants.getByRole('button', { name: 'Выключить остальные' }).click()
  await expect(black).not.toBeChecked()
  await variants.getByRole('textbox', { name: 'Поиск варианта' }).fill('Цвет: Чёрный · Размер: 42')
  await expect(variants.getByRole('row')).toHaveCount(2)
  await variants.getByRole('button', { name: 'Сделать главным: Цвет: Чёрный · Размер: 42', exact: true }).click()
  await expect(variants.getByText('Главный', { exact: true })).toBeVisible()
  await expect(black).toBeChecked()
  await expect(black).toBeDisabled()
  await expect(page.locator('.detail-header__product')).toContainText('Чёрный')
  await page.getByRole('button', { name: 'Изменить', exact: true }).click()
  await expect(page.getByRole('textbox', { name: 'Артикул', exact: true })).toHaveValue(seed)
  await expect(page.getByLabel('Ссылка (необязательно)')).toHaveValue('https://www.ozon.ru/product/2936649562/')
  await page.getByRole('button', { name: 'Сохранить', exact: true }).click()
  await expect(page.getByRole('dialog', { name: 'Изменить товар' })).toBeHidden()
  for (const width of [1440, 1024]) {
    await page.setViewportSize({ width, height: 1000 })
    await expect.poll(() => page.evaluate(() => window.document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    await expect(variants).toBeVisible()
  }
  await expect(page.locator('vite-error-overlay')).toHaveCount(0)
  await page.screenshot({ path: '/tmp/price-watch-ozon-variants-1024.png', fullPage: false })
  expect(errors).toEqual([])
})
