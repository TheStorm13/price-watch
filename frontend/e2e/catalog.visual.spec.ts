import { expect, test } from '@playwright/test'
import { uiFixture } from './uiFixtures'

test('каталог, формы и детали с согласованной геометрией', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await uiFixture(page)
  await expect(page).toHaveTitle('price-watch')
  await expect(page.locator('vite-error-overlay')).toHaveCount(0)
  await expect(page).toHaveScreenshot('catalog-list.png')
  await page.getByRole('radio', { name: 'Сетка', exact: true }).click()
  await expect(page).toHaveScreenshot('catalog-grid.png')
  await page.getByRole('textbox', { name: 'Поиск карточек' }).fill('1598827711')
  await expect(page.locator('.cards-grid__item')).toHaveCount(1)
  await page.setViewportSize({ width: 1024, height: 700 })
  await expect(page).toHaveScreenshot('catalog-single.png')
  await page.getByRole('textbox', { name: 'Поиск карточек' }).fill('')
  await page.getByRole('button', { name: 'Создать группу', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveScreenshot('group-dialog.png')
  await page.keyboard.press('Escape')
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.getByRole('button', { name: 'Добавить карточку', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveScreenshot('add-drawer.png')
  await page.keyboard.press('Escape')
  await page.locator('.cards-grid__link').filter({ hasText: 'Очень длинное название' }).click()
  await expect(page.getByLabel('График цен всех SKU')).toBeVisible()
  for (const width of [1024, 1440, 1920]) {
    await page.setViewportSize({ width, height: 900 })
    await expect(page).toHaveScreenshot(`details-${width}.png`)
  }
  await page.getByRole('button',{name:'Изменить',exact:true}).click()
  await expect(page.getByRole('dialog',{name:'Изменить карточку'})).toHaveScreenshot('edit-drawer.png')
})

test('группа в каталоге', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await uiFixture(page, true)
  await expect(page.locator('.cards-table__group')).toBeVisible()
  await expect(page).toHaveScreenshot('group-list.png')
  await page.getByRole('radio', { name: 'Сетка', exact: true }).click()
  await expect(page).toHaveScreenshot('group-grid.png')
})

for (const status of ['running', 'waiting_for_user', 'completed_with_errors'] as const) {
  test(`панель сбора ${status}`, async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 700 })
    await uiFixture(page, false, status)
    const panel = page.getByLabel('Состояние обновления цен')
    await expect(panel).toBeVisible()
    if (status === 'completed_with_errors') await panel.getByText('Показать ошибки', { exact: true }).click()
    await expect(panel).toHaveScreenshot(`collection-${status}.png`)
  })
}
