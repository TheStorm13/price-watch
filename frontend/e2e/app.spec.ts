import { expect, test } from '@playwright/test'

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
  await page.getByRole('button', { name: /Действия с карточкой/ }).click()
  await expect(page.getByRole('menuitem', { name: 'Приостановить отслеживание' })).toBeVisible()
  await expect(page.getByRole('menuitem', { name: 'Удалить карточку' })).toBeVisible()
  await page.keyboard.press('Escape')
  await page.screenshot({ path: '/tmp/price-watch-detail.png' })
  expect(errors).toEqual([])
})

test('компактный desktop 1024 px не имеет горизонтального overflow', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 })
  await page.goto('/cards')
  await expect(page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })).toBeVisible()
  const hasOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
  expect(hasOverflow).toBe(false)
})

test('меню карточки явно приостанавливает и возобновляет отслеживание', async ({ page }) => {
  await page.goto('/cards')
  const row = page.getByRole('row', { name: /Смартфон Samsung Galaxy S24/ })
  await row.getByRole('button', { name: /Действия с карточкой/ }).click()
  await expect(page.getByRole('menuitem', { name: 'Приостановить отслеживание' })).toBeVisible()
  await page.getByRole('menuitem', { name: 'Приостановить отслеживание' }).click()
  await expect(row.getByText('Отслеживание приостановлено')).toBeVisible()

  await row.getByRole('button', { name: /Действия с карточкой/ }).click()
  await expect(page.getByRole('menuitem', { name: 'Возобновить отслеживание' })).toBeVisible()
  await page.screenshot({ path: '/tmp/price-watch-card-actions.png' })
  await page.getByRole('menuitem', { name: 'Возобновить отслеживание' }).click()
  await expect(row.getByText('Отслеживание приостановлено')).toBeHidden()
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
  await expect(page.getByText('Требуется проверка Ozon')).toBeVisible({ timeout: 8_000 })
  await page.getByRole('button', { name: 'Проверка пройдена' }).click()
  await expect(page.getByText('Цены обновлены')).toBeVisible({ timeout: 8_000 })
})

test('детали карточки показывают середину диапазона и страницы истории', async ({ page }) => {
  await page.goto('/cards/1')
  await expect(page.getByText('Середина диапазона')).toBeVisible()
  await expect(page.getByText('77 240 ₽', { exact: true })).toBeVisible()
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

test('одиночное измерение остаётся точкой на графике с нулевой осью', async ({ page }) => {
  await page.goto('/cards/2')
  const chart = page.getByLabel('График истории цены')
  await expect(chart).toBeVisible()
  await expect(chart.locator('.recharts-line-dot')).toHaveCount(1)
  await expect(chart.getByText('0', { exact: true })).toBeVisible()
})
