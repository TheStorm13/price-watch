import { expect, test } from '@playwright/test'

test('WB: размеры сохраняются в одной карточке и имеет действие обновления', async ({ page }) => {
  await page.goto('/cards')
  for (const size of ['296499716', '296499717']) {
    await page.getByRole('button', { name: 'Добавить карточку' }).click()
    await page.getByRole('radio', { name: /Wildberries/ }).click()
    await expect(page.getByRole('button', { name: 'Добавить', exact: true })).toBeDisabled()
    await page.getByLabel('URL', { exact: true }).fill(`https://www.wildberries.ru/catalog/179224846/detail.aspx?size=${size}`)
    await expect(page.getByLabel('Артикул WB')).toHaveValue('179224846')
    await expect(page.getByLabel('Код размера WB')).toHaveValue(size)
    await page.getByLabel('Название', { exact: true }).fill(`WB размер ${size}`)
    await page.getByRole('button', { name: 'Добавить', exact: true }).click()
    await expect(page.getByRole('dialog')).toHaveCount(0)
    await expect(page.locator('.cards-table')).not.toContainText(`179224846:${size}`)
    await page.getByRole('link', { name: 'WB размер 296499716', exact: true }).click()
    await expect(page.getByText('ID 179224846', { exact: true })).toBeVisible()
    await page.getByRole('link', { name: 'К карточкам' }).click()
  }
  await page.getByText('WB размер 296499716', { exact: true }).click()
  await expect(page.getByRole('button', { name: /Обновить/ }).first()).toBeEnabled()
})
