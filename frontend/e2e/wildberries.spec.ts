import { expect, test } from '@playwright/test'

test('WB: ссылка с размером добавляет товар без ручного выбора варианта', async ({ page }) => {
  await page.goto('/cards')
  await page.getByRole('button', { name: 'Добавить карточку' }).click()
  await page.getByRole('radio', { name: /Wildberries/ }).click()
  await expect(page.getByRole('button', { name: 'Добавить', exact: true })).toBeDisabled()
  await page.getByLabel('URL', { exact: true }).fill('https://www.wildberries.ru/catalog/179224846/detail.aspx?size=296499716')
  await expect(page.getByLabel('Артикул WB')).toHaveValue('179224846')
  await expect(page.getByLabel('Код размера WB')).toHaveCount(0)
  await page.getByLabel('Название', { exact: true }).fill('WB товар')
  await page.getByRole('button', { name: 'Добавить', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.locator('.cards-table')).not.toContainText('179224846:296499716')
  await page.getByRole('link', { name: 'WB товар', exact: true }).click()
  await expect(page.getByText('ID 179224846', { exact: true })).toBeVisible()
  await expect(page.getByRole('main').getByRole('button', { name: 'Обновить эту карточку', exact: true })).toBeEnabled()
})
