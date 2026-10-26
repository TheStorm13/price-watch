import { expect, test } from '@playwright/test'

test('AliExpress: ссылка заполняет точный SKU и создаёт отдельную карточку', async ({ page }) => {
  await page.goto('/cards')
  await page.getByRole('button', { name: 'Добавить карточку' }).click()
  await page.getByRole('radio', { name: /AliExpress/ }).click()
  await expect(page.getByRole('button', { name: 'Добавить', exact: true })).toBeDisabled()
  await page.getByLabel('URL', { exact: true }).fill('https://aliexpress.ru/item/1005009868651525.html?sku_id=12000061135122688')
  await expect(page.getByLabel('ID товара')).toHaveValue('1005009868651525')
  await expect(page.getByLabel('SKU варианта')).toHaveValue('12000061135122688')
  await page.getByLabel('Название', { exact: true }).fill('Ali SKU smoke')
  await page.screenshot({ path: '/tmp/price-watch-ali-add-card.png', fullPage: false })
  await page.getByRole('button', { name: 'Добавить', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.getByText('1005009868651525:12000061135122688', { exact: false })).toBeVisible()
})
