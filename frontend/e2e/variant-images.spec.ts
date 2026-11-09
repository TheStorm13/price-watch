import { expect, test } from '@playwright/test'

test('варианты показывают свои фото, а карточка переключает все данные главного', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.route('https://images.test/missing.webp', (route) => route.fulfill({ status: 404, body: '' }))
  const image = (color: string) => `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="120" height="180"><rect width="120" height="180" fill="${color}"/></svg>`)}`
  const photos = [image('black'), image('white'), 'https://images.test/missing.webp']
  const titles = ['Чёрная куртка', 'Белая куртка', 'Куртка без фото']
  const colors = ['чёрный', 'белый', 'серый']
  const now = new Date().toISOString()
  const transfer = { version: 3, cards: [{ marketplace: 'wildberries', externalId: '812345678',
    title: titles[0], url: null, imageUrl: photos[0], createdAt: now, dealsEnabled: true,
    primaryExternalId: '812345678:1', variants: titles.map((title, i) => ({
      externalId: `812345678:${i + 1}`, title: colors[i], productTitle: title,
      imageUrl: photos[i], options: { Цвет: colors[i] }, updatedAt: now,
      url: `https://www.wildberries.ru/catalog/812345678/detail.aspx?size=${i + 1}`,
      history: [{ price: String((i + 1) * 100), availability: 'in_stock', observedAt: now }],
    })),
  }] }
  await page.goto('/cards')
  await page.getByLabel('Импорт / экспорт').click()
  await page.getByRole('menuitem', { name: 'Импорт', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Импорт карточек и истории' })
  await dialog.locator('input[type="file"]').setInputFiles({ name: 'variants.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(transfer)) })
  await expect(dialog).toContainText('Добавлено карточек: 1')
  await dialog.getByRole('button', { name: 'Импортировать' }).click()
  await page.getByRole('link', { name: titles[0], exact: true }).click()
  await expect(page).toHaveURL(/\/cards\/\d+$/)
  await expect(page).toHaveTitle('Price watch')
  await expect(page.locator('vite-error-overlay')).toHaveCount(0)
  const variants = page.getByRole('region', { name: 'Варианты товара' })
  await expect(variants.locator('.product-placeholder')).toHaveCount(3)
  await expect(variants.locator('.variant-name strong')).toHaveText(['Цвет: белый', 'Цвет: серый', 'Цвет: чёрный'])
  await expect(variants).not.toContainText('812345678')
  await expect(variants).not.toContainText('Код варианта')
  for (const width of [1440, 1024]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    await expect(variants).toBeVisible()
  }
  await page.getByRole('button', { name: 'Сделать главным: Цвет: белый', exact: true }).click()
  await expect(page.getByRole('heading', { name: titles[1], exact: true })).toBeVisible()
  await expect(page.locator('.detail-header__product img')).toHaveAttribute('src', /^blob:/)
  await expect(page.getByRole('link', { name: 'Открыть на Wildberries' })).toHaveAttribute('href', /size=2$/)
  await expect(page.locator('.price-summary__primary strong')).toContainText('200')
  await expect(page.locator('.price-stat').first()).toContainText('200')
  await expect(page.getByRole('checkbox', { name: 'Показать на графике: Цвет: белый', exact: true })).toBeChecked()
  await expect(page.getByRole('checkbox', { name: 'Показать на графике: Цвет: чёрный', exact: true })).not.toBeChecked()
  await expect(page.locator('.detail-header__meta')).toContainText('Цвет: белый')
  await page.locator('.recharts-line-dot').first().hover()
  await expect(page.locator('.recharts-tooltip-wrapper')).toBeVisible()
  await expect(page.locator('.recharts-tooltip-wrapper')).toContainText('Цвет: белый')
  await expect(page.locator('.recharts-tooltip-wrapper')).not.toContainText('Вариант 2')
  await page.screenshot({ path: '/tmp/pw-variant-images-1024.png', fullPage: false })
  await page.getByRole('button', { name: 'Сделать главным: Цвет: серый', exact: true }).click()
  await expect(page.getByRole('heading', { name: titles[2], exact: true })).toBeVisible()
  await expect(page.locator('.detail-header__product img')).toHaveCount(0)
  expect(await page.locator('body').innerText()).not.toContain('SKU')
  expect(errors).toEqual([])
})
