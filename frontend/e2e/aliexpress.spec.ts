import { expect, test } from '@playwright/test'

test('AliExpress: ссылка с вариантом заполняет артикул товара', async ({ page }) => {
  await page.goto('/cards')
  await page.getByRole('button', { name: 'Добавить карточку' }).click()
  await page.getByRole('radio', { name: /AliExpress/ }).click()
  await expect(page.getByRole('button', { name: 'Добавить', exact: true })).toBeDisabled()
  await page.getByLabel('URL', { exact: true }).fill('https://aliexpress.ru/item/1005009868651525.html?sku_id=12000061135122688')
  await expect(page.getByLabel('ID товара')).toHaveValue('1005009868651525')
  await expect(page.getByLabel('SKU варианта')).toHaveCount(0)
  await page.getByLabel('Название', { exact: true }).fill('Ali вариант smoke')
  await page.getByRole('button', { name: 'Добавить', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.locator('.cards-table')).not.toContainText('1005009868651525:12000061135122688')
  await page.getByRole('link', { name: 'Ali вариант smoke', exact: true }).click()
  await expect(page.getByText('ID 1005009868651525', { exact: true })).toBeVisible()
})
